"""
Shift ClickUp task start_date and due_date by a delta computed from an ANCHOR task.

What you do:
- Point to a folder (lists inside it)
- Pick an anchor task (by ID or by name substring)
- Provide the new anchor date (YYYY-MM-DD)
- Script computes delta_ms = new_anchor_date - old_anchor_date
- Applies delta_ms to start_date and due_date across tasks (only if those fields exist)

SAFE DEFAULTS:
- Only updates fields that already exist on the task (it will NOT set start_date/due_date to null).
- Supports dry-run.
- Supports validate-ids to confirm folder and lists before changing anything.
- If anchor name matches multiple tasks, it aborts and prints candidates.

Usage:
  # Validate folder/lists
  python scripts/shift_clickup_dates.py --folder-id <FOLDER_ID> --validate-ids

  # Dry-run using anchor by task ID
  python scripts/shift_clickup_dates.py --folder-id <FOLDER_ID> --anchor-task-id <TASK_ID> --new-anchor-date 2026-01-15 --dry-run

  # Dry-run using anchor by name substring (case-insensitive)
  python scripts/shift_clickup_dates.py --folder-id <FOLDER_ID> --anchor-task-name "Workshop" --new-anchor-date 2026-01-15 --dry-run

  # Execute for real (after dry-run looks correct)
  python scripts/shift_clickup_dates.py --folder-id <FOLDER_ID> --anchor-task-id <TASK_ID> --new-anchor-date 2026-01-15

Env (.env or environment):
  CLICKUP_TOKEN=pk_xxx

Optional:
  CLICKUP_INCLUDE_CLOSED=true|false  (default false)
  CLICKUP_ANCHOR_FIELD=due|start     (default due)  # which field defines the workshop date on the anchor
"""

import os
import sys
import time
import json
import argparse
from typing import Dict, Any, Iterator, List, Optional, Set, Tuple

from datetime import datetime, date, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

CLICKUP_TOKEN = os.getenv("CLICKUP_TOKEN")
if not CLICKUP_TOKEN:
    print("Error: CLICKUP_TOKEN is required (set in .env or environment).")
    sys.exit(1)

API_BASE = "https://api.clickup.com/api/v2"
HEADERS = {"Authorization": CLICKUP_TOKEN, "Content-Type": "application/json"}

DEFAULT_PAGE_SIZE = 100
INCLUDE_CLOSED = os.getenv("CLICKUP_INCLUDE_CLOSED", "false").strip().lower() in ("1", "true", "yes")

ANCHOR_FIELD = os.getenv("CLICKUP_ANCHOR_FIELD", "due").strip().lower()
if ANCHOR_FIELD not in ("due", "start"):
    ANCHOR_FIELD = "due"


def request_with_retry(method: str, url: str, *, params=None, json_body=None, max_retries: int = 8) -> Dict[str, Any]:
    backoff = 1.0
    for _ in range(1, max_retries + 1):
        resp = requests.request(method, url, headers=HEADERS, params=params, json=json_body, timeout=60)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            sleep_s = float(retry_after) if retry_after else backoff
            time.sleep(min(sleep_s, 15.0))
            backoff = min(backoff * 1.7, 15.0)
            continue

        if 500 <= resp.status_code < 600:
            time.sleep(min(backoff, 15.0))
            backoff = min(backoff * 1.7, 15.0)
            continue

        try:
            resp.raise_for_status()
        except Exception:
            print(f"HTTP error on {method} {url}: {resp.status_code} {resp.text}")
            raise

        if resp.text.strip() == "":
            return {}
        return resp.json()

    raise RuntimeError(f"Max retries exceeded for {method} {url}")


def get_folder_lists(folder_id: str) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/folder/{folder_id}/list"
    data = request_with_retry("GET", url)
    return data.get("lists", [])


def iter_list_tasks(list_id: str, page_size: int = DEFAULT_PAGE_SIZE) -> Iterator[Dict[str, Any]]:
    url = f"{API_BASE}/list/{list_id}/task"
    page = 0

    while True:
        params = {
            "page": page,
            "include_closed": str(INCLUDE_CLOSED).lower(),
            "subtasks": "true",
            "include_markdown_description": "false",
        }
        data = request_with_retry("GET", url, params=params)
        tasks = data.get("tasks", []) or []

        for t in tasks:
            yield t

        if len(tasks) < page_size:
            break

        page += 1


def parse_csv_ids(value: Optional[str]) -> Optional[Set[str]]:
    if not value:
        return None
    return {v.strip() for v in value.split(",") if v.strip()}


def parse_epoch_ms(raw) -> Optional[int]:
    if raw in (None, "", 0, "0"):
        return None
    try:
        return int(raw)
    except Exception:
        return None


def compute_new_anchor_ms(old_anchor_ms: int, new_anchor_date_str: str) -> int:
    """
    We preserve the time-of-day from the old anchor datetime (UTC),
    and swap only the date to new_anchor_date (YYYY-MM-DD), in UTC.
    This avoids shifting everything by hours unintentionally.
    """
    old_dt = datetime.fromtimestamp(old_anchor_ms / 1000.0, tz=timezone.utc)

    new_d = datetime.strptime(new_anchor_date_str, "%Y-%m-%d").date()
    new_dt = datetime(
        year=new_d.year, month=new_d.month, day=new_d.day,
        hour=old_dt.hour, minute=old_dt.minute, second=old_dt.second, microsecond=0,
        tzinfo=timezone.utc
    )
    return int(new_dt.timestamp() * 1000)


def build_update_payload_by_delta(task: Dict[str, Any], delta_ms: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}

    start_ms = parse_epoch_ms(task.get("start_date"))
    due_ms = parse_epoch_ms(task.get("due_date"))

    # Only update fields that exist
    if start_ms is not None:
        payload["start_date"] = int(start_ms + delta_ms)
    if due_ms is not None:
        payload["due_date"] = int(due_ms + delta_ms)

    return payload


def update_task(task_id: str, payload: Dict[str, Any], dry_run: bool) -> None:
    if not payload:
        return
    if dry_run:
        return
    url = f"{API_BASE}/task/{task_id}"
    request_with_retry("PUT", url, json_body=payload)


def find_anchor_task(
    lists: List[Dict[str, Any]],
    include_lists: Optional[Set[str]],
    exclude_lists: Optional[Set[str]],
    anchor_task_id: Optional[str],
    anchor_task_name: Optional[str],
) -> Tuple[Dict[str, Any], str]:
    """
    Search tasks in the folder lists and find the anchor.
    Returns: (task_dict, list_id)
    """
    name_query = anchor_task_name.strip().lower() if anchor_task_name else None
    matches: List[Tuple[Dict[str, Any], str]] = []

    for lst in lists:
        list_id = str(lst.get("id"))
        if include_lists and list_id not in include_lists:
            continue
        if exclude_lists and list_id in exclude_lists:
            continue

        for task in iter_list_tasks(list_id):
            tid = str(task.get("id"))
            tname = (task.get("name") or "")

            if anchor_task_id and tid == anchor_task_id:
                return task, list_id

            if name_query and name_query in tname.lower():
                matches.append((task, list_id))

    if anchor_task_id:
        raise RuntimeError("Anchor task ID not found in the lists scanned.")

    if name_query:
        if len(matches) == 0:
            raise RuntimeError("No anchor task matched by name substring in the lists scanned.")
        if len(matches) > 1:
            print("Multiple anchor candidates found. Please use --anchor-task-id, or make the name more specific.")
            for t, lid in matches[:25]:
                print(f"- list_id={lid} task_id={t.get('id')} name={t.get('name')}")
            raise RuntimeError("Ambiguous anchor name match.")
        return matches[0]

    raise RuntimeError("You must provide --anchor-task-id or --anchor-task-name.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Shift ClickUp task dates based on an anchor task's new date.")
    parser.add_argument("--folder-id", required=True, help="Folder ID containing the lists to process.")
    parser.add_argument("--dry-run", action="store_true", help="Do not perform PUT updates, only log.")
    parser.add_argument("--include-lists", help="Comma-separated list IDs to include.")
    parser.add_argument("--exclude-lists", help="Comma-separated list IDs to exclude.")
    parser.add_argument("--validate-ids", action="store_true", help="Only validate folder/list IDs and exit.")

    # Anchor mode
    parser.add_argument("--anchor-task-id", help="Exact ClickUp task ID for the anchor task.")
    parser.add_argument("--anchor-task-name", help="Substring to find the anchor task by name (case-insensitive).")
    parser.add_argument("--new-anchor-date", help="New anchor date in YYYY-MM-DD (required unless --validate-ids).")

    args = parser.parse_args()

    include_lists = parse_csv_ids(args.include_lists)
    exclude_lists = parse_csv_ids(args.exclude_lists)

    lists = get_folder_lists(args.folder_id)
    if not lists:
        print("No lists returned for this folder-id.")
        print("Likely causes: folder-id changed, token has no access, wrong workspace, folder archived.")
        sys.exit(2)

    # Filter lists
    filtered_lists = []
    for lst in lists:
        list_id = str(lst.get("id"))
        if include_lists and list_id not in include_lists:
            continue
        if exclude_lists and list_id in exclude_lists:
            continue
        filtered_lists.append(lst)

    print("Lists to process:")
    for lst in filtered_lists:
        print(f"- {lst.get('name')} (id={lst.get('id')})")

    if args.validate_ids:
        print("\nvalidate-ids done. No task updates performed.")
        return

    if not args.new_anchor_date:
        print("Error: --new-anchor-date is required (YYYY-MM-DD).")
        sys.exit(1)

    # Find anchor
    anchor_task, anchor_list_id = find_anchor_task(
        filtered_lists,
        include_lists=None,  # already filtered above
        exclude_lists=None,
        anchor_task_id=args.anchor_task_id,
        anchor_task_name=args.anchor_task_name,
    )
    print("\nAnchor task found:")
    print(f"- list_id={anchor_list_id} task_id={anchor_task.get('id')} name={anchor_task.get('name')}")

    # Determine old anchor date field
    old_anchor_ms = None
    if ANCHOR_FIELD == "due":
        old_anchor_ms = parse_epoch_ms(anchor_task.get("due_date"))
        field_name = "due_date"
    else:
        old_anchor_ms = parse_epoch_ms(anchor_task.get("start_date"))
        field_name = "start_date"

    if old_anchor_ms is None:
        print(f"Error: Anchor task has no {field_name}. Set it first (or change CLICKUP_ANCHOR_FIELD).")
        sys.exit(1)

    new_anchor_ms = compute_new_anchor_ms(old_anchor_ms, args.new_anchor_date)
    delta_ms = new_anchor_ms - old_anchor_ms

    delta_days = delta_ms / (86400 * 1000)
    print(f"\nAnchor field used: {field_name}")
    print(f"Old anchor ms: {old_anchor_ms}")
    print(f"New anchor ms: {new_anchor_ms}")
    print(f"Computed delta: {delta_ms} ms (~{delta_days:.2f} days)")

    total_tasks = 0
    would_update = 0
    updated = 0
    samples: List[Dict[str, Any]] = []

    for lst in filtered_lists:
        list_id = str(lst.get("id"))
        list_name = lst.get("name")
        print(f"\nProcessing list: {list_name} (id={list_id})")

        for task in iter_list_tasks(list_id):
            total_tasks += 1
            task_id = str(task.get("id"))

            payload = build_update_payload_by_delta(task, delta_ms)

            # If this is the anchor task, also ensure its anchor field lands exactly on new date
            # (It will naturally shift by delta, but this makes intent explicit if you prefer.)
            if task_id == str(anchor_task.get("id")) and payload:
                pass  # keep payload as-is; it's correct with delta.

            if payload:
                would_update += 1
                if len(samples) < 8:
                    samples.append(
                        {
                            "task_id": task_id,
                            "name": task.get("name"),
                            "old_start_date": task.get("start_date"),
                            "old_due_date": task.get("due_date"),
                            "payload": payload,
                        }
                    )

                if not args.dry_run:
                    update_task(task_id, payload, dry_run=False)
                    updated += 1

    print("\n====== Summary ======")
    print(f"Total tasks scanned: {total_tasks}")
    print(f"Tasks with dates to shift: {would_update}")
    print(f"Tasks updated (dry-run=false): {updated}")
    print("\nSamples (up to 8):")
    for s in samples:
        print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
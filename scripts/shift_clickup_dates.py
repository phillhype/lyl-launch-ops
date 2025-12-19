"""
Shift ClickUp task start_date and due_date by N days for all tasks in all lists inside a folder.

SAFE DEFAULTS:
- Only updates fields that already exist on the task (it will NOT set start_date/due_date to null).
- Supports dry-run.
- Supports validate-ids to confirm folder and list IDs/names before changing anything.

Usage:
  python scripts/shift_clickup_dates.py --folder-id <FOLDER_ID> --days <N> --dry-run
  python scripts/shift_clickup_dates.py --folder-id <FOLDER_ID> --days <N> --validate-ids
  python scripts/shift_clickup_dates.py --folder-id <FOLDER_ID> --days <N> --include-lists 123,456
  python scripts/shift_clickup_dates.py --folder-id <FOLDER_ID> --days <N> --exclude-lists 123,456

Env (.env or environment):
  CLICKUP_TOKEN=pk_xxx
Optional:
  CLICKUP_INCLUDE_CLOSED=true|false  (default false)

Notes:
- ClickUp dates are epoch milliseconds (as strings in API responses).
- This script will keep "start_date_time" and "due_date_time" flags unchanged if present, but will not add them.
"""

import os
import sys
import time
import json
import argparse
from typing import Dict, Any, Iterator, List, Optional, Set

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


def shift_epoch_ms(epoch_ms: Optional[int], days: int) -> Optional[int]:
    if epoch_ms is None:
        return None
    return int(epoch_ms + (days * 86400 * 1000))


def request_with_retry(method: str, url: str, *, params=None, json_body=None, max_retries: int = 8) -> Dict[str, Any]:
    backoff = 1.0
    for attempt in range(1, max_retries + 1):
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


def build_update_payload(task: Dict[str, Any], days: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}

    # ClickUp returns date fields as strings (epoch ms) or None.
    start_raw = task.get("start_date")
    due_raw = task.get("due_date")

    start_ms = int(start_raw) if start_raw not in (None, "", 0, "0") else None
    due_ms = int(due_raw) if due_raw not in (None, "", 0, "0") else None

    new_start = shift_epoch_ms(start_ms, days) if start_ms is not None else None
    new_due = shift_epoch_ms(due_ms, days) if due_ms is not None else None

    # Only include keys that already exist (avoid clearing fields).
    if start_ms is not None and new_start != start_ms:
        payload["start_date"] = new_start
    if due_ms is not None and new_due != due_ms:
        payload["due_date"] = new_due

    return payload


def update_task_dates(task_id: str, payload: Dict[str, Any], dry_run: bool) -> None:
    if not payload:
        return
    if dry_run:
        return
    url = f"{API_BASE}/task/{task_id}"
    request_with_retry("PUT", url, json_body=payload)


def parse_csv_ids(value: Optional[str]) -> Optional[Set[str]]:
    if not value:
        return None
    return {v.strip() for v in value.split(",") if v.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Shift ClickUp task start_date and due_date by N days.")
    parser.add_argument("--folder-id", required=True, help="Folder ID containing the lists to process.")
    parser.add_argument("--days", type=int, required=True, help="Days to shift (positive or negative).")
    parser.add_argument("--dry-run", action="store_true", help="Do not perform PUT updates, only log.")
    parser.add_argument("--include-lists", help="Comma-separated list IDs to include.")
    parser.add_argument("--exclude-lists", help="Comma-separated list IDs to exclude.")
    parser.add_argument("--validate-ids", action="store_true", help="Only validate folder/list IDs and exit.")
    args = parser.parse_args()

    include_lists = parse_csv_ids(args.include_lists)
    exclude_lists = parse_csv_ids(args.exclude_lists)

    lists = get_folder_lists(args.folder_id)
    if not lists:
        print("No lists returned for this folder-id.")
        print("Likely causes: folder-id changed, token has no access, wrong workspace/team context, or folder is archived.")
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
            task_name = task.get("name", "")

            payload = build_update_payload(task, args.days)
            if payload:
                would_update += 1

                # collect a few samples
                if len(samples) < 8:
                    samples.append(
                        {
                            "task_id": task_id,
                            "name": task_name,
                            "payload": payload,
                            "old_start_date": task.get("start_date"),
                            "old_due_date": task.get("due_date"),
                        }
                    )

                if not args.dry_run:
                    update_task_dates(task_id, payload, dry_run=False)
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
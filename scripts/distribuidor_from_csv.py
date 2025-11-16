import os, sys, csv, json, time
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()
API   = "https://api.clickup.com/api/v2"
TOKEN = os.getenv("CLICKUP_TOKEN")
TEAM  = os.getenv("CLICKUP_TEAM")
HEAD  = {"Authorization": TOKEN, "Content-Type": "application/json"}

if not TOKEN or not TEAM:
    print("Erro: defina CLICKUP_TOKEN e CLICKUP_TEAM no .env")
    sys.exit(1)

CACHE_MAP = os.path.join("scripts", ".cache_lists_map.json")

DATE_INPUT_FORMATS = ["%d/%m/%Y","%d/%m"]  # cai no ano atual se faltar ano
YEAR_DEFAULT = int(os.getenv("LAUNCH_YEAR", datetime.now().year))

def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in DATE_INPUT_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%d/%m":
                dt = dt.replace(year=YEAR_DEFAULT)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return None

def post(url, payload):
    for _ in range(5):
        r = requests.post(url, headers=HEAD, json=payload, timeout=40)
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 429:
            time.sleep(2)
            continue
        # se campo inválido, não travar o lote
        print(f"[WARN] POST {url} status={r.status_code} body={r.text[:300]}")
        return None
    return None

def get(url, params=None):
    for _ in range(5):
        r = requests.get(url, headers=HEAD, params=params, timeout=40)
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 429:
            time.sleep(2)
            continue
        print(f"[WARN] GET {url} status={r.status_code} body={r.text[:300]}")
        return None
    return None

def load_map():
    if not os.path.exists(CACHE_MAP):
        print("Erro: não encontrei", CACHE_MAP, "rode `make retrofit` antes.")
        sys.exit(1)
    with open(CACHE_MAP, "r", encoding="utf-8") as f:
        return json.load(f)["lists"]

def norm_key(s):
    return (s or "").strip().lower()

def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [ {k.strip(): (v or "").strip() for k,v in row.items()} for row in reader ]
    return rows

# tentativa de normalização de chaves
KEYS_MAP = {
    "nome": "nome",
    "task": "nome",
    "tarefa": "nome",
    "expert": "expert",
    "área padrão": "area_padrao",
    "area_padrao": "area_padrao",
    "área": "area_padrao",
    "area": "area_padrao",
    "sprint": "sprint",
    "fase": "fase",
    "tipo": "tipo",
    "grupo": "grupo",
    "status": "status",
    "data inicial": "Data inicial",
    "data final": "Data final",
    "dificuldade": "Dificuldade",
    "duração": "Duração",
    "prioridade": "Prioridade",
    "checkpoint": "Checkpoint",
}

def normalize_row(row):
    out = {}
    for k,v in row.items():
        k2 = KEYS_MAP.get(norm_key(k), k)
        out[k2] = v
    return out

def ensure_tags(list_id):
    # Nada a fazer. Tags são por tarefa, não por lista.
    return

def create_task(list_id, row):
    name = row.get("nome") or "(sem título)"
    status = row.get("status") or "Programado"
    start = parse_date(row.get("Data inicial"))
    due   = parse_date(row.get("Data final"))
    expert_tag = row.get("expert")
    priority_map = {
        "baixa":1,"moderada":2,"alta":3,"crítica":4,"critica":4
    }
    prio = priority_map.get(norm_key(row.get("Prioridade","")), None)

    payload = {
        "name": name,
        "status": status,
        "priority": prio,
        "start_date": str(start) if start else None,
        "due_date": str(due) if due else None,
        "start_date_time": False,
        "due_date_time": False,
        "tags": [expert_tag] if expert_tag else []
    }
    # remove None
    payload = {k:v for k,v in payload.items() if v not in (None, "", [])}
    res = post(f"{API}/list/{list_id}/task", payload)
    if not res or "id" not in res:
        print(f"[ERRO] Falha criando task '{name}' na lista {list_id}")
        return None
    return res["id"]

def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/distribuidor_from_csv.py caminho/arquivo.csv")
        sys.exit(1)
    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print("CSV não encontrado:", csv_path)
        sys.exit(1)

    lists_map = load_map()
    rows = read_csv(csv_path)
    total = 0; ok = 0; skip = 0

    for raw in rows:
        total += 1
        row = normalize_row(raw)
        area = norm_key(row.get("area_padrao",""))
        list_id = lists_map.get(area)

        if not list_id:
            print(f"[SKIP] Linha {total}: área '{area}' sem mapeamento. Rode `make retrofit` e confira os nomes.")
            skip += 1
            continue

        ensure_tags(list_id)
        tid = create_task(list_id, row)
        if tid:
            ok += 1
        else:
            skip += 1
        time.sleep(0.15)  # evitar 429

    print(f"\nResumo: total={total} criadas_ok={ok} puladas={skip}")

if __name__ == "__main__":
    main()

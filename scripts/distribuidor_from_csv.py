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
OVERRIDE_MAP = os.path.join("scripts", "lists_map.override.json")

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
    """Carrega mapeamento de áreas -> list_ids
    Prioridade: override.json > cache.json
    """
    if os.path.exists(OVERRIDE_MAP):
        print(f"📝 Usando mapeamento de: {OVERRIDE_MAP}")
        with open(OVERRIDE_MAP, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mapping", {})

    if not os.path.exists(CACHE_MAP):
        print("Erro: não encontrei", CACHE_MAP, "nem", OVERRIDE_MAP)
        print("Rode `make retrofit` antes.")
        sys.exit(1)

    print(f"💾 Usando mapeamento de: {CACHE_MAP}")
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
    "data inicial": "data_inicial",
    "data inicial relativa": "data_inicial",
    "data_inicio_relativa": "data_inicial",
    "data final": "data_final",
    "data final relativa": "data_final",
    "data_entrega_relativa": "data_final",
    "dificuldade": "dificuldade",
    "duração": "duracao_dias",
    "duracao_dias": "duracao_dias",
    "prioridade": "prioridade",
    "checkpoint": "checkpoint",
}

def normalize_row(row):
    out = {}
    for k,v in row.items():
        k2 = KEYS_MAP.get(norm_key(k), k)
        out[k2] = v
    return out

def get_custom_fields(list_id):
    """Busca custom fields da lista"""
    try:
        data = get(f"{API}/list/{list_id}/field")
        return {f['name'].lower(): f for f in data.get('fields', [])}
    except:
        return {}

def create_task(list_id, row, dry_run=False):
    name = row.get("nome") or "(sem título)"
    status = row.get("status") or "backlog"
    start = parse_date(row.get("data_inicial"))
    due   = parse_date(row.get("data_final"))
    expert_tag = row.get("expert")

    priority_map = {
        "baixa":1,"moderada":2,"alta":3,"crítica":4,"critica":4
    }
    prio = priority_map.get(norm_key(row.get("prioridade","")), None)

    # Detectar checkpoint
    is_checkpoint = norm_key(row.get("checkpoint", "")) in ["sim", "true", "1", "x"]

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

    # Custom fields (sprint, fase, tipo, dificuldade, duracao_dias, grupo)
    custom_fields = []

    # Buscar custom fields da lista (só se não for dry-run)
    if not dry_run:
        fields_def = get_custom_fields(list_id)

        # Sprint (text)
        if row.get("sprint") and "sprint" in fields_def:
            custom_fields.append({
                "id": fields_def["sprint"]["id"],
                "value": row["sprint"]
            })

        # Fase (dropdown)
        if row.get("fase") and "fase" in fields_def:
            custom_fields.append({
                "id": fields_def["fase"]["id"],
                "value": row["fase"]
            })

        # Tipo (dropdown)
        if row.get("tipo") and "tipo" in fields_def:
            custom_fields.append({
                "id": fields_def["tipo"]["id"],
                "value": row["tipo"]
            })

        # Dificuldade (dropdown)
        if row.get("dificuldade") and "dificuldade" in fields_def:
            custom_fields.append({
                "id": fields_def["dificuldade"]["id"],
                "value": row["dificuldade"]
            })

        # Duração dias (number)
        if row.get("duracao_dias") and "duracao_dias" in fields_def:
            try:
                custom_fields.append({
                    "id": fields_def["duracao_dias"]["id"],
                    "value": int(row["duracao_dias"])
                })
            except ValueError:
                pass

        # Grupo (text)
        if row.get("grupo") and "grupo" in fields_def:
            custom_fields.append({
                "id": fields_def["grupo"]["id"],
                "value": row["grupo"]
            })

        # Checkpoint (boolean/checkbox)
        if is_checkpoint and "checkpoint" in fields_def:
            custom_fields.append({
                "id": fields_def["checkpoint"]["id"],
                "value": True
            })

    if custom_fields:
        payload["custom_fields"] = custom_fields

    # remove None
    payload = {k:v for k,v in payload.items() if v not in (None, "", [])}

    if dry_run:
        return {"id": "DRY_RUN", "url": f"https://app.clickup.com/{TEAM}/t/DRY_RUN"}

    res = post(f"{API}/list/{list_id}/task", payload)
    if not res or "id" not in res:
        print(f"[ERRO] Falha criando task '{name}' na lista {list_id}")
        return None
    return res

def get_list_name(list_id):
    """Busca o nome da lista pelo ID"""
    try:
        data = get(f"{API}/list/{list_id}")
        return data.get("name", f"List {list_id}")
    except:
        return f"List {list_id}"

def main():
    dry_run = "--dry-run" in sys.argv

    # Remover --dry-run da lista de argumentos
    args = [a for a in sys.argv[1:] if a != "--dry-run"]

    if len(args) < 1:
        print("Uso: python scripts/distribuidor_from_csv.py caminho/arquivo.csv [--dry-run]")
        sys.exit(1)

    csv_path = args[0]
    if not os.path.exists(csv_path):
        print("CSV não encontrado:", csv_path)
        sys.exit(1)

    print("=" * 60)
    if dry_run:
        print("🧪 MODO DRY-RUN - Nenhuma tarefa será criada")
    else:
        print("🚀 MODO PRODUÇÃO - Tarefas serão criadas no ClickUp")
    print("=" * 60)

    lists_map = load_map()

    # Verificar se há listas não mapeadas
    unmapped_areas = [k for k,v in lists_map.items() if v is None]
    if unmapped_areas:
        print("\n⚠️ ATENÇÃO: As seguintes áreas não estão mapeadas:")
        for area in unmapped_areas:
            print(f"  - {area}")
        print("\nTarefas dessas áreas serão PULADAS.")
        print(f"Edite {OVERRIDE_MAP} para corrigir o mapeamento.\n")

    rows = read_csv(csv_path)
    total = 0
    ok = 0
    skip = 0
    created_tasks = []

    print(f"\n📄 Processando {len(rows)} linhas do CSV...\n")

    for idx, raw in enumerate(rows, 1):
        total += 1
        row = normalize_row(raw)
        area = norm_key(row.get("area_padrao",""))

        # Checkpoint override
        is_checkpoint = norm_key(row.get("checkpoint", "")) in ["sim", "true", "1", "x"]
        if is_checkpoint and "checkpoints" in lists_map and lists_map["checkpoints"]:
            area = "checkpoints"

        list_id = lists_map.get(area)

        if not list_id:
            if dry_run and idx <= 10:
                print(f"❌ [{idx:3d}] SKIP: '{row.get('nome', '(sem nome)')[:40]}' → área '{area}' não mapeada")
            if not dry_run:
                print(f"[SKIP] Linha {total}: área '{area}' sem mapeamento.")
            skip += 1
            continue

        # Dry-run: mostrar apenas primeiras 10 linhas
        if dry_run and idx <= 10:
            list_name = get_list_name(list_id)
            task_name = row.get("nome", "(sem nome)")[:50]
            print(f"✅ [{idx:3d}] '{task_name}' → Lista: '{list_name}' (ID: {list_id})")

        # Produção: criar tarefa real
        if not dry_run:
            task = create_task(list_id, row, dry_run=False)
            if task:
                ok += 1
                created_tasks.append({
                    "name": row.get("nome", "(sem nome)"),
                    "url": task.get("url", f"https://app.clickup.com/{TEAM}/t/{task['id']}"),
                    "area": area
                })
                if ok % 10 == 0:
                    print(f"  ✓ {ok} tarefas criadas...")
            else:
                skip += 1
            time.sleep(0.15)  # evitar 429

    print("\n" + "=" * 60)
    print("📊 RESUMO")
    print("=" * 60)
    print(f"Total de linhas: {total}")
    if dry_run:
        print(f"Tarefas que SERIAM criadas: {total - skip}")
        print(f"Tarefas que seriam PULADAS: {skip}")
        print("\n💡 Para criar as tarefas de verdade, rode sem --dry-run")
    else:
        print(f"Tarefas criadas com sucesso: {ok}")
        print(f"Tarefas puladas/erro: {skip}")

        if created_tasks:
            print("\n🔗 EXEMPLOS DE TAREFAS CRIADAS:")
            # Mostrar 5 tarefas de áreas diferentes
            shown_areas = set()
            shown = 0
            for task in created_tasks:
                if task["area"] not in shown_areas and shown < 5:
                    print(f"  • [{task['area']}] {task['name']}")
                    print(f"    {task['url']}")
                    shown_areas.add(task["area"])
                    shown += 1
                if shown >= 5:
                    break

    print("=" * 60)

if __name__ == "__main__":
    main()

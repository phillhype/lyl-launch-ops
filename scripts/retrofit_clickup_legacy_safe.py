import os, sys, json, time, re
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://api.clickup.com/api/v2"
TOKEN = os.getenv("CLICKUP_TOKEN")
TEAM  = os.getenv("CLICKUP_TEAM")

if not TOKEN or not TEAM:
    print("Erro: defina CLICKUP_TOKEN e CLICKUP_TEAM no .env")
    sys.exit(1)

HEAD = {"Authorization": TOKEN, "Content-Type": "application/json"}

AREAS_CANON = [
    "projetos","estrategia","copy","social_media","design","edicao_de_videos",
    "trafego","infra_automacoes","comercial","suporte","checkpoints"
]

CACHE_PATH = os.path.join("scripts", ".cache_lists_map.json")

def get(url, params=None):
    for _ in range(5):
        r = requests.get(url, headers=HEAD, params=params, timeout=30)
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 429:
            time.sleep(2)
            continue
        r.raise_for_status()
    raise RuntimeError("GET falhou repetidamente")

def find_space_id_by_name(team_id, name_like):
    data = get(f"{API}/team/{team_id}/space")
    for sp in data.get("spaces", []):
        if sp["name"].strip().lower() == name_like.strip().lower():
            return sp["id"]
    return None

def collect_lists_in_space(space_id):
    lists = []

    # listas no root do space
    try:
        data = get(f"{API}/space/{space_id}/list")
        lists += data.get("lists", [])
    except Exception:
        pass

    # listas dentro de pastas
    try:
        fd = get(f"{API}/space/{space_id}/folder")
        for folder in fd.get("folders", []):
            ld = get(f"{API}/folder/{folder['id']}/list")
            lists += ld.get("lists", [])
    except Exception:
        pass
    return lists

def normalize_name(n):
    n = n.strip().lower()
    n = re.sub(r"[^\w]+", "_", n)
    return n

def main():
    op_space = find_space_id_by_name(TEAM, "Operação LYL")
    if not op_space:
        print("❌ Space 'Operação LYL' não encontrado. Crie-o antes.")
        sys.exit(1)

    all_lists = collect_lists_in_space(op_space)
    by_norm = { normalize_name(l["name"]): l for l in all_lists }

    wanted = {a: None for a in AREAS_CANON}
    for key in by_norm:
        if key in wanted:
            wanted[key] = by_norm[key]["id"]

    print("🔎 Detecção de listas no Space 'Operação LYL':")
    for area, lid in wanted.items():
        print(f"  - {area}: {'OK ' + lid if lid else 'NÃO ENCONTRADA'}")

    # salva cache
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"space_id": op_space, "lists": wanted}, f, ensure_ascii=False, indent=2)

    faltando = [a for a, lid in wanted.items() if lid is None]
    if faltando:
        print("\n⚠️ Listas NÃO encontradas (use nomes exatos). Crie-as manualmente OU ajuste os nomes para corresponder:")
        print("   " + ", ".join(faltando))
    else:
        print("\n✅ Mapeamento concluído e salvo em", CACHE_PATH)

if __name__ == "__main__":
    main()

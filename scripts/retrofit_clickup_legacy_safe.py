import os, sys, json, time, re
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://api.clickup.com/api/v2"
TOKEN = os.getenv("CLICKUP_TOKEN")
TEAM  = os.getenv("CLICKUP_TEAM")
SPACE_ID = os.getenv("CLICKUP_SPACE_ID")  # Opcional: se definido, pula busca por nome

if not TOKEN or not TEAM:
    print("Erro: defina CLICKUP_TOKEN e CLICKUP_TEAM no .env")
    sys.exit(1)

HEAD = {"Authorization": TOKEN, "Content-Type": "application/json"}

# Mapeamento de áreas canônicas para nomes conhecidos das listas antigas
AREA_SYNONYMS = {
    "projetos": ["Planejamentos & Cronogramas", "Planejamentos", "Cronogramas", "Projetos"],
    "estrategia": ["Estratégias & Funis", "Estrategias", "Funis", "Estratégia"],
    "copy": ["Processo de Copywriting", "Copywriting", "Copy"],
    "social_media": ["Agendamentos & Publicações", "Agendamentos", "Publicações", "Social Media", "Social"],
    "design": ["Design & Criação", "Design", "Criação", "Criacao"],
    "edicao_de_videos": ["Gravação & Edição", "Gravacao", "Edicao", "Edição", "Videos", "Vídeos"],
    "trafego": ["Gestão de Campanhas", "Campanhas", "Tráfego", "Trafego", "Ads", "Performance"],
    "infra_automacoes": ["Processos de Automações", "Automacoes", "Automações", "Desenvolvimento Web", "Landing Page", "Manutenção & Atualizações"],
    "comercial": ["Comercial", "Vendas"],
    "suporte": ["Suporte", "Atendimento"],
    "checkpoints": ["checkpoints", "Checkpoints", "Check-points"]
}

AREAS_CANON = list(AREA_SYNONYMS.keys())

CACHE_PATH = os.path.join("scripts", ".cache_lists_map.json")
OVERRIDE_PATH = os.path.join("scripts", "lists_map.override.json")

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
        root_lists = data.get("lists", [])
        lists += root_lists
        print(f"  → Listas no root do Space: {len(root_lists)}")
        for lst in root_lists:
            print(f"     • '{lst['name']}' (ID: {lst['id']})")
    except Exception as e:
        print(f"  ⚠️ Erro ao buscar listas no root: {e}")

    # listas dentro de pastas
    try:
        fd = get(f"{API}/space/{space_id}/folder")
        folders = fd.get("folders", [])
        print(f"  → Pastas encontradas: {len(folders)}")
        for folder in folders:
            print(f"     • Pasta: '{folder['name']}' (ID: {folder['id']})")
            ld = get(f"{API}/folder/{folder['id']}/list")
            folder_lists = ld.get("lists", [])
            print(f"       - Listas na pasta: {len(folder_lists)}")
            for lst in folder_lists:
                print(f"         ◦ '{lst['name']}' (ID: {lst['id']})")
            lists += folder_lists
    except Exception as e:
        print(f"  ⚠️ Erro ao buscar pastas/listas: {e}")
    return lists

def normalize_name(n):
    """Normaliza nome removendo acentos, pontuação e convertendo para lowercase"""
    import unicodedata
    n = unicodedata.normalize('NFD', n)
    n = ''.join(c for c in n if unicodedata.category(c) != 'Mn')
    n = n.strip().lower()
    n = re.sub(r"[^\w\s]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n

def fuzzy_match(list_name, synonyms):
    """Verifica se o nome da lista corresponde a algum sinônimo"""
    norm_list = normalize_name(list_name)
    for syn in synonyms:
        norm_syn = normalize_name(syn)
        # Match exato
        if norm_list == norm_syn:
            return True
        # Match parcial (contém)
        if norm_syn in norm_list or norm_list in norm_syn:
            return True
    return False

def auto_map_lists(all_lists):
    """Mapeia automaticamente listas para áreas usando sinônimos"""
    mapping = {area: None for area in AREAS_CANON}
    mapping_details = {area: {"list_id": None, "list_name": None, "matched_synonym": None} for area in AREAS_CANON}

    # Criar um dicionário de listas já mapeadas para evitar duplicatas
    used_lists = set()

    for area, synonyms in AREA_SYNONYMS.items():
        for lst in all_lists:
            if lst['id'] in used_lists:
                continue
            if fuzzy_match(lst['name'], synonyms):
                mapping[area] = lst['id']
                mapping_details[area] = {
                    "list_id": lst['id'],
                    "list_name": lst['name'],
                    "matched_synonym": "auto-matched"
                }
                used_lists.add(lst['id'])
                break

    return mapping, mapping_details

def main():
    print("=" * 60)
    print("🔄 RETROFIT - Mapeamento de Listas EXISTENTES")
    print("=" * 60)

    # Usar SPACE_ID do .env se fornecido, senão buscar por nome
    if SPACE_ID:
        print(f"✅ Usando Space ID do .env: {SPACE_ID}")
        op_space = SPACE_ID
    else:
        print("🔍 Buscando Space 'Operação LYL' pelo nome...")
        op_space = find_space_id_by_name(TEAM, "Operação LYL")
        if not op_space:
            print("❌ Space 'Operação LYL' não encontrado.")
            sys.exit(1)
        print(f"✅ Space encontrado: {op_space}")

    print("\n📂 Coletando listas do Space...")
    all_lists = collect_lists_in_space(op_space)

    if not all_lists:
        print("\n⚠️ NENHUMA lista encontrada no Space!")
        print("Possíveis causas:")
        print("  1. Token sem permissão para ler listas/folders")
        print("  2. Space vazio")
        print("  3. Space ID incorreto")
        print("\nPróximos passos:")
        print("  - Crie um novo token com permissões: View Spaces, View Folders, View Lists")
        print("  - OU forneça os List IDs manualmente em lists_map.override.json")
        sys.exit(1)

    print(f"\n📋 Total de listas encontradas: {len(all_lists)}")

    # Auto-mapeamento
    print("\n🤖 Realizando mapeamento automático com sinônimos...")
    mapping, mapping_details = auto_map_lists(all_lists)

    # Mostrar resultado do mapeamento
    print("\n" + "=" * 60)
    print("📊 RESULTADO DO MAPEAMENTO")
    print("=" * 60)

    mapped = []
    unmapped = []

    for area in AREAS_CANON:
        details = mapping_details[area]
        if details['list_id']:
            mapped.append(area)
            print(f"✅ {area:20} → '{details['list_name']}' (ID: {details['list_id']})")
        else:
            unmapped.append(area)
            print(f"❌ {area:20} → NÃO MAPEADA")

    # Salvar cache
    cache_data = {
        "space_id": op_space,
        "generated_at": datetime.now().isoformat(),
        "lists": mapping,
        "details": mapping_details,
        "all_lists_found": [{"id": l['id'], "name": l['name']} for l in all_lists]
    }

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Cache salvo em: {CACHE_PATH}")

    # Gerar override se necessário
    if unmapped:
        print("\n" + "=" * 60)
        print("⚠️ LISTAS NÃO MAPEADAS")
        print("=" * 60)
        print(f"As seguintes áreas não foram mapeadas automaticamente:")
        for area in unmapped:
            print(f"  - {area}")
            print(f"    Sinônimos esperados: {', '.join(AREA_SYNONYMS[area])}")

        # Gerar arquivo de override
        override_data = {
            "_comment": "Edite este arquivo para mapear manualmente áreas para List IDs",
            "_instructions": "Substitua null pelo List ID correto (número)",
            "_available_lists": [{"id": l['id'], "name": l['name']} for l in all_lists],
            "mapping": {area: mapping[area] for area in AREAS_CANON}
        }

        with open(OVERRIDE_PATH, "w", encoding="utf-8") as f:
            json.dump(override_data, f, ensure_ascii=False, indent=2)

        print(f"\n📝 Arquivo de override gerado: {OVERRIDE_PATH}")
        print("Edite este arquivo para corrigir mapeamentos manualmente.")
        print("Após editar, rode novamente 'make distribute' (ele usará o override).")
    else:
        print("\n" + "=" * 60)
        print("✅ SUCESSO - Todas as áreas foram mapeadas!")
        print("=" * 60)
        print("Próximo passo: rodar 'make distribute CSV=/caminho/arquivo.csv --dry-run'")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

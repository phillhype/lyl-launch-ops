# Quick Start - Distribuição de Tarefas (Estrutura Existente)

## ✅ O que você precisa fazer (5 passos)

### 1. Pegar os List IDs do ClickUp

Abra cada lista no ClickUp web e copie o **List ID** da URL:

```
https://app.clickup.com/9013265478/v/li/901234567890
                                         ^^^^^^^^^^^^
                                         Este é o List ID
```

**Listas que você precisa:**
- Planejamentos & Cronogramas
- Estratégias & Funis
- Processo de Copywriting
- Agendamentos & Publicações
- Design & Criação
- Gravação & Edição
- Gestão de Campanhas
- Gestão de Fluxos / Processos de Automações

**Opcional (se quiser sub-roteamento de infra/tráfego):**
- Landing Pages
- Manutenção & Atualizações
- Gestão de Domínios & Hospedagens
- WhatsApps
- Processo de Otimização

---

### 2. Criar `scripts/lists_map.override.json`

```bash
cp scripts/lists_map.override.json.example scripts/lists_map.override.json
```

Edite o arquivo e substitua os placeholders pelos IDs reais:

```json
{
  "mapping": {
    "projetos": "901234567890",
    "estrategia": "901234567891",
    "copy": "901234567892",
    "social_media": "901234567893",
    "design": "901234567894",
    "edicao_de_videos": "901234567895",
    "trafego": "901234567896",
    "infra_automacoes": "901234567897"
  }
}
```

---

### 3. (Opcional) Configurar sub-roteamento

Se você quer que tarefas de `infra_automacoes` vão para listas diferentes baseado em palavra-chave:

```bash
cp scripts/routing_rules.json.example scripts/routing_rules.json
```

Edite e preencha com os List IDs das listas específicas:

```json
{
  "rules": {
    "infra_automacoes": {
      "by_group_contains": [
        {
          "match": ["LP", "Landing Page", "landing"],
          "list_id": "901234567898",
          "description": "Landing Pages"
        },
        {
          "match": ["manutencao", "manutenção", "update"],
          "list_id": "901234567899",
          "description": "Manutenção"
        }
      ]
    }
  }
}
```

**Como funciona:**
- Se o campo `grupo` da tarefa contém "LP", vai pra lista de Landing Pages
- Se contém "manutenção", vai pra lista de Manutenção
- Se não bater nenhuma regra, vai pra lista default de `infra_automacoes`

---

### 4. Testar com dry-run

```bash
make distribute CSV="/caminho/para/seu_arquivo.csv" DRY_RUN=1
```

**Saída esperada:**
```
======================================================================
🧪 MODO DRY-RUN - Nenhuma tarefa será criada
======================================================================
📝 Usando mapeamento de: scripts/lists_map.override.json

📄 Processando 150 linhas do CSV...

[OK] Definir posicionamento do produto -> estrategia -> 901234567891
[OK] Escrever copy da página de vendas -> copy -> 901234567892
[OK] Criar mockup da landing page -> design -> 901234567894
[OK] Tarefa com checkpoint [CHECKPOINT] -> copy -> 901234567892
[OK] Criar LP do produto -> infra_automacoes -> 901234567898 (roteado por regra)
...
```

**Valide que:**
- ✅ Cada tarefa aponta para o List ID correto
- ✅ Checkpoints aparecem marcados como `[CHECKPOINT]`
- ✅ Sub-roteamento funciona (se configurou `routing_rules.json`)

---

### 5. Distribuir de verdade

```bash
make distribute CSV="/caminho/para/seu_arquivo.csv"
```

**Saída esperada:**
```
======================================================================
🚀 MODO PRODUÇÃO - Tarefas serão criadas no ClickUp
======================================================================
📝 Usando mapeamento de: scripts/lists_map.override.json

📄 Processando 150 linhas do CSV...

  ✓ 10 tarefas criadas...
  ✓ 20 tarefas criadas...
  ...
  ✓ 145 tarefas criadas...

======================================================================
📊 RESUMO
======================================================================
Total de linhas: 150
Tarefas criadas com sucesso: 145
Tarefas puladas/erro: 5

🔗 EXEMPLOS DE TAREFAS CRIADAS:
  • [estrategia] Definir posicionamento do produto
    https://app.clickup.com/9013265478/t/abc123
  • [copy] Escrever copy da página de vendas
    https://app.clickup.com/9013265478/t/def456
  ...
======================================================================
```

---

## 📋 Formato do CSV

O CSV deve ter estas colunas:

| Coluna obrigatória | Descrição |
|--------------------|-----------|
| `nome` | Nome da tarefa |
| `área padrão` | Área: copy, design, social_media, etc. |

| Coluna opcional | Descrição |
|-----------------|-----------|
| `expert` | Nome do expert (vira tag) |
| `sprint` | Sprint (texto) |
| `fase` | Fase (dropdown) |
| `tipo` | Tipo (dropdown) |
| `status` | Status inicial (backlog, em andamento, etc.) |
| `data inicial` | Data início (DD/MM ou DD/MM/YYYY) |
| `data final` | Data entrega (DD/MM ou DD/MM/YYYY) |
| `dificuldade` | Dificuldade (dropdown) |
| `duração` | Duração em dias (número) |
| `grupo` | Grupo (texto) - usado para sub-roteamento |
| `prioridade` | Prioridade (baixa, moderada, alta, crítica) |
| `checkpoint` | Checkpoint (sim/true/1/x) |

**Checkpoint:**
- Tarefas com `checkpoint=sim` terão o campo custom `checkpoint=true` marcado
- Permanecerão na lista da área (não vão para lista separada)
- Discord/automações disparam quando o checkpoint for concluído

---

## 🐛 Troubleshooting

### Erro: "contém placeholders não preenchidos"

**Causa:** Você não substituiu os `SUBSTITUIR_PELO_ID_...` pelos IDs reais

**Solução:** Edite `scripts/lists_map.override.json` e coloque os List IDs copiados do ClickUp

### Erro: "área não mapeada"

**Causa:** O CSV tem uma área que não existe no `lists_map.override.json`

**Solução:** Adicione a área no mapeamento ou corrija o CSV

### Tarefas indo para lista errada

**Causa:** List ID incorreto ou regra de roteamento errada

**Solução:**
1. Verifique os List IDs em `lists_map.override.json`
2. Se usar sub-roteamento, valide `routing_rules.json`
3. Rode dry-run para confirmar antes de criar

### Custom fields não aparecem

**Causa:** Lista não tem os custom fields criados

**Solução:** No ClickUp, crie manualmente os campos:
- `sprint` (texto)
- `fase` (dropdown)
- `tipo` (dropdown)
- `dificuldade` (dropdown)
- `duracao_dias` (número)
- `grupo` (texto)
- `checkpoint` (checkbox)

---

## 🔒 Segurança

- ✅ `lists_map.override.json` e `routing_rules.json` estão no `.gitignore`
- ✅ Nenhum List ID é commitado
- ✅ Apenas arquivos `.example` vão para o Git

---

## ⚡ Comandos rápidos

```bash
# 1. Preparar ambiente
make install

# 2. Criar configuração
cp scripts/lists_map.override.json.example scripts/lists_map.override.json
# Editar e preencher IDs

# 3. Testar
make distribute CSV="arquivo.csv" DRY_RUN=1

# 4. Distribuir
make distribute CSV="arquivo.csv"
```

**Pronto!** 🚀

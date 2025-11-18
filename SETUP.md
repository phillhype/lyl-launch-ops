# Setup - Distribuição de Tarefas do CSV para ClickUp

## ✅ O que foi implementado

Sistema completo para distribuir tarefas de um CSV para listas **EXISTENTES** no ClickUp, preservando:
- ✅ Estrutura antiga (listas, pastas, automações)
- ✅ Status flows (backlog → em andamento → em revisão → aprovado → concluído)
- ✅ Custom fields (sprint, fase, tipo, dificuldade, duração, grupo, checkpoint)
- ✅ Mapeamento automático com fuzzy matching
- ✅ Dry-run para validação antes de criar tarefas

---

## 📋 Estratégia: PRESERVAR estrutura existente

**O que NÃO fazemos:**
- ❌ Criar novas listas/pastas
- ❌ Renomear ou deletar listas
- ❌ Modificar automações

**O que fazemos:**
- ✅ Mapear listas existentes automaticamente
- ✅ Criar tarefas nas listas antigas
- ✅ Preservar automações e fluxos de trabalho

---

## 🗺️ Mapeamento de áreas

O sistema mapeia automaticamente estas áreas canônicas para suas listas existentes:

| Área Canônica       | Nomes Esperados (sinônimos)                                      |
|---------------------|------------------------------------------------------------------|
| `projetos`          | Planejamentos & Cronogramas, Planejamentos, Cronogramas         |
| `estrategia`        | Estratégias & Funis, Estrategias, Funis                         |
| `copy`              | Processo de Copywriting, Copywriting, Copy                      |
| `social_media`      | Agendamentos & Publicações, Agendamentos, Social Media          |
| `design`            | Design & Criação, Design, Criação                               |
| `edicao_de_videos`  | Gravação & Edição, Gravacao, Edicao, Videos                     |
| `trafego`           | Gestão de Campanhas, Campanhas, Tráfego, Ads                   |
| `infra_automacoes`  | Processos de Automações, Desenvolvimento Web, Landing Page      |
| `comercial`         | Comercial, Vendas                                                |
| `suporte`           | Suporte, Atendimento                                             |
| `checkpoints`       | checkpoints, Checkpoints                                         |

O fuzzy matching remove acentos e normaliza nomes para facilitar o match.

---

## 🚀 Fluxo de uso

### 1. Criar token ClickUp com permissões corretas

No ClickUp:
1. Settings (⚙️) → Apps → API Tokens
2. Criar novo token com estas permissões:
   - ✅ **View Spaces** (ler spaces)
   - ✅ **View Folders** (ler pastas)
   - ✅ **View Lists** (ler listas)
   - ✅ **View Custom Fields** (ler campos customizados)
   - ✅ **View Tasks** (ler tarefas)
   - ✅ **Create Tasks** (criar tarefas)
   - ✅ **Edit Tasks** (editar tarefas - para custom fields)

### 2. Configurar .env

```bash
cp .env.example .env
# Editar e preencher:
CLICKUP_TOKEN=pk_seu_token_aqui_SEM_ASPAS
CLICKUP_TEAM=9013265478
CLICKUP_SPACE_ID=901311487992
LAUNCH_YEAR=2025
```

### 3. Instalar dependências

```bash
make install
```

### 4. Retrofit - Mapear listas existentes

```bash
make retrofit
```

**Saída esperada:**
- Lista todas as pastas e listas do Space "Operação LYL"
- Mapeia automaticamente usando fuzzy matching
- Gera `scripts/.cache_lists_map.json` com o mapeamento
- Se algo não mapear, gera `scripts/lists_map.override.json` para edição manual

**Exemplo de saída:**
```
============================================================
🔄 RETROFIT - Mapeamento de Listas EXISTENTES
============================================================
✅ Usando Space ID do .env: 901311487992

📂 Coletando listas do Space...
  → Pastas encontradas: 3
     • Pasta: 'Conteúdo' (ID: 123456)
       - Listas na pasta: 4
         ◦ 'Processo de Copywriting' (ID: 789)
         ◦ 'Design & Criação' (ID: 790)
         ...

📋 Total de listas encontradas: 15

🤖 Realizando mapeamento automático com sinônimos...

============================================================
📊 RESULTADO DO MAPEAMENTO
============================================================
✅ copy                → 'Processo de Copywriting' (ID: 789)
✅ design              → 'Design & Criação' (ID: 790)
✅ social_media        → 'Agendamentos & Publicações' (ID: 791)
...
❌ comercial           → NÃO MAPEADA
❌ suporte             → NÃO MAPEADA

💾 Cache salvo em: scripts/.cache_lists_map.json

============================================================
⚠️ LISTAS NÃO MAPEADAS
============================================================
As seguintes áreas não foram mapeadas automaticamente:
  - comercial
    Sinônimos esperados: Comercial, Vendas
  - suporte
    Sinônimos esperados: Suporte, Atendimento

📝 Arquivo de override gerado: scripts/lists_map.override.json
Edite este arquivo para corrigir mapeamentos manualmente.
```

### 5. (Opcional) Corrigir mapeamento manual

Se houver áreas não mapeadas, edite `scripts/lists_map.override.json`:

```json
{
  "_comment": "Edite este arquivo para mapear manualmente áreas para List IDs",
  "_available_lists": [
    {"id": "789", "name": "Processo de Copywriting"},
    {"id": "792", "name": "Vendas & Atendimento"}
  ],
  "mapping": {
    "copy": "789",
    "comercial": "792",  // ← Mapear manualmente
    "suporte": "792",    // ← Mapear manualmente
    ...
  }
}
```

### 6. Dry-run - Testar sem criar tarefas

```bash
make distribute CSV="/caminho/para/seu_arquivo.csv" DRY_RUN=1
```

**Saída esperada:**
```
============================================================
🧪 MODO DRY-RUN - Nenhuma tarefa será criada
============================================================
💾 Usando mapeamento de: scripts/.cache_lists_map.json

📄 Processando 150 linhas do CSV...

✅ [  1] 'Definir posicionamento do produto' → Lista: 'Estratégias & Funis' (ID: 788)
✅ [  2] 'Escrever copy da página de vendas' → Lista: 'Processo de Copywriting' (ID: 789)
✅ [  3] 'Criar mockup da landing page' → Lista: 'Design & Criação' (ID: 790)
...
✅ [ 10] 'Checkpoint 1: Validar estratégia' → Lista: 'checkpoints' (ID: 800)

============================================================
📊 RESUMO
============================================================
Total de linhas: 150
Tarefas que SERIAM criadas: 145
Tarefas que seriam PULADAS: 5

💡 Para criar as tarefas de verdade, rode sem --dry-run
============================================================
```

### 7. Distribuição real

```bash
make distribute CSV="/caminho/para/seu_arquivo.csv"
```

**Saída esperada:**
```
============================================================
🚀 MODO PRODUÇÃO - Tarefas serão criadas no ClickUp
============================================================
💾 Usando mapeamento de: scripts/.cache_lists_map.json

📄 Processando 150 linhas do CSV...

  ✓ 10 tarefas criadas...
  ✓ 20 tarefas criadas...
  ...
  ✓ 145 tarefas criadas...

============================================================
📊 RESUMO
============================================================
Total de linhas: 150
Tarefas criadas com sucesso: 145
Tarefas puladas/erro: 5

🔗 EXEMPLOS DE TAREFAS CRIADAS:
  • [estrategia] Definir posicionamento do produto
    https://app.clickup.com/9013265478/t/123abc
  • [copy] Escrever copy da página de vendas
    https://app.clickup.com/9013265478/t/456def
  • [design] Criar mockup da landing page
    https://app.clickup.com/9013265478/t/789ghi
  • [social_media] Agendar posts de lançamento
    https://app.clickup.com/9013265478/t/012jkl
  • [checkpoints] Checkpoint 1: Validar estratégia
    https://app.clickup.com/9013265478/t/345mno
============================================================
```

---

## 📝 Formato do CSV

O CSV deve ter estas colunas (case-insensitive, aceita variações):

| Coluna                          | Descrição                                    | Obrigatório |
|---------------------------------|----------------------------------------------|-------------|
| `nome` / `tarefa` / `task`      | Nome da tarefa                               | ✅          |
| `área padrão` / `area_padrao`   | Área (copy, design, social_media, etc.)      | ✅          |
| `expert`                        | Nome do expert (vira tag)                    | ❌          |
| `sprint`                        | Sprint (texto)                               | ❌          |
| `fase`                          | Fase (dropdown)                              | ❌          |
| `tipo`                          | Tipo (dropdown)                              | ❌          |
| `status`                        | Status inicial (backlog, em andamento, etc.) | ❌          |
| `data inicial` / `data_inicio_relativa` | Data início (DD/MM ou DD/MM/YYYY)    | ❌          |
| `data final` / `data_entrega_relativa`  | Data entrega (DD/MM ou DD/MM/YYYY)   | ❌          |
| `dificuldade`                   | Dificuldade (dropdown)                       | ❌          |
| `duração` / `duracao_dias`      | Duração em dias (número)                     | ❌          |
| `grupo`                         | Grupo (texto)                                | ❌          |
| `prioridade`                    | Prioridade (baixa, moderada, alta, crítica)  | ❌          |
| `checkpoint`                    | Checkpoint (sim/true/1/x)                    | ❌          |

**Checkpoint especial:**
- Linhas com `checkpoint=sim` vão automaticamente para a lista "checkpoints" (se existir)
- Campo custom `checkpoint=true` é marcado na tarefa

---

## 🔧 Comandos disponíveis

```bash
make help           # Mostrar ajuda
make install        # Instalar dependências Python
make retrofit       # Mapear listas existentes
make distribute CSV=/caminho/arquivo.csv DRY_RUN=1  # Testar sem criar
make distribute CSV=/caminho/arquivo.csv            # Criar tarefas
make check-env      # Debug: mostrar variáveis de ambiente
```

---

## 🐛 Troubleshooting

### Erro: HTTP 403 Forbidden

**Causa:** Token sem permissões necessárias

**Solução:**
1. Deletar token atual no ClickUp
2. Criar novo token com TODAS as permissões listadas acima
3. Atualizar `.env` com novo token

### Erro: "Space não encontrado"

**Causa:** `CLICKUP_SPACE_ID` incorreto

**Solução:**
1. Abra o ClickUp web
2. Entre no Space "Operação LYL"
3. Copie o ID da URL: `https://app.clickup.com/9013265478/v/li/XXXXXXXXX`
4. Atualize `CLICKUP_SPACE_ID` no `.env`

### Erro: "Área não mapeada"

**Causa:** Lista não existe ou nome diferente do esperado

**Solução:**
1. Rode `make retrofit` para ver todas as listas
2. Edite `scripts/lists_map.override.json` manualmente
3. Rode novamente `make distribute`

### Custom fields não aparecem

**Causa:** Lista não tem os custom fields criados

**Solução:**
1. No ClickUp, vá na lista
2. Crie os custom fields manualmente:
   - `sprint` (texto)
   - `fase` (dropdown)
   - `tipo` (dropdown)
   - `dificuldade` (dropdown)
   - `duracao_dias` (número)
   - `grupo` (texto)
   - `checkpoint` (checkbox/boolean)

---

## 📂 Arquivos importantes

```
lyl-launch-ops/
├── .env                                    # Credenciais (NÃO commitar)
├── .env.example                            # Template do .env
├── Makefile                                # Comandos make
├── requirements.txt                        # Dependências Python
├── scripts/
│   ├── retrofit_clickup_legacy_safe.py    # Mapeia listas existentes
│   ├── distribuidor_from_csv.py           # Distribui tarefas do CSV
│   ├── .cache_lists_map.json             # Cache do mapeamento (gerado)
│   └── lists_map.override.json            # Override manual (gerado)
└── SETUP.md                                # Este arquivo
```

---

## ✅ Próximos passos (Felipe)

1. **Criar token ClickUp** com permissões corretas
2. **Atualizar .env** com novo token
3. **Rodar `make retrofit`** para mapear listas
4. **Validar mapeamento** (se necessário, editar override)
5. **Testar dry-run** com CSV
6. **Distribuir tarefas** reais
7. **Validar** algumas tarefas criadas no ClickUp

---

## 🔒 Segurança

- ✅ `.env` está no `.gitignore`
- ✅ Nenhum token é commitado
- ✅ Cache files (`.cache_*.json`) são ignorados
- ✅ Apenas operações de leitura (retrofit) e criação de tarefas (distribute)
- ✅ Nenhuma modificação de estrutura (listas/pastas/automações)

---

Dúvidas? Veja os logs detalhados ao rodar cada comando!

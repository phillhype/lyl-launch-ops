# Operacional – Visão Rápida

- **Estrutura anterior (listas antigas)** é preservada. Não rebatizamos listas nem alteramos automations existentes.
- O CSV do **espelho de lançamento** é importado pelo `scripts/distribuidor_from_csv.py`, que:
  - Mapeia `area_padrao` -> lista operacional correspondente.
  - Cria a tarefa na lista **original** (modelo antigo), com `tags` do expert, datas e status.
  - Tenta preencher campos personalizados se existirem. Se não existir, registra aviso (não quebra).

- O `scripts/retrofit_clickup_legacy_safe.py`:
  - Descobre o Space **"Operação LYL"** e coleta listas (root e pastas).
  - Gera `scripts/.cache_lists_map.json` com IDs das listas **sem alterar nada**.
  - Mapeamento de áreas (padrão):
    - projetos -> `projetos`
    - estrategia -> `estrategia`
    - copy -> `copy`
    - social_media -> `social_media`
    - design -> `design`
    - edicao_de_videos -> `edicao_de_videos`
    - trafego -> `trafego`
    - infra_automacoes -> `infra_automacoes`
    - comercial -> `comercial`
    - suporte -> `suporte`
    - checkpoints -> `checkpoints`

## Campos esperados no CSV
- `nome` (string)
- `expert` (string; será adicionado como **tag** na task)
- `area_padrao` (uma das áreas acima)
- `sprint` (ex.: s-8)
- `fase` (ex.: "Fase 0. Definições Preliminares")
- `tipo` (post/lancamento/institucional)
- `grupo` (ex.: Abertura, Produção [PPL], etc.)
- `status` (ex.: Programado, Em aprovação, Em revisão, Aprovado, Agendado, Concluído, Cancelado, Atrasado)
- `Data inicial` (dd/mm ou dd/mm/yyyy)
- `Data final` (dd/mm ou dd/mm/yyyy)
- `Dificuldade` (Fácil/Moderada/Difícil/Muito Difícil)
- `Duração` (Muito curta/Curta/Moderada/Longa/Muito longa)
- `Prioridade` (Baixa/Moderada/Alta/Crítica)
- `Checkpoint` (TRUE/FALSE ou vazio)

> Observação: se seu CSV já tem cabeçalho ligeiramente diferente, o `distribuidor_from_csv.py` tenta normalizar chaves por aproximação.

## Segurança
- Nunca commitar `.env` ou webhooks reais.
- Se usar CI/CD, guarde tokens em **GitHub Secrets**.

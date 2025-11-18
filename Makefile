.PHONY: help install retrofit distribute check-env

help:
	@echo "Comandos:"
	@echo "  make install       -> cria venv e instala deps"
	@echo "  make retrofit      -> mapeia listas EXISTENTES no Space 'Operação LYL'"
	@echo "  make distribute CSV=/caminho/arquivo.csv [DRY_RUN=1] -> distribui tarefas do CSV"
	@echo "  make check-env     -> mostra variáveis lidas do .env (debug)"

install:
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

retrofit:
	. .venv/bin/activate && export $$(grep -v '^#' .env | xargs) && \
	python3 scripts/retrofit_clickup_legacy_safe.py

distribute:
	@[ -n "$(CSV)" ] || (echo "Erro: informe CSV=/caminho/arquivo.csv" && exit 1)
	. .venv/bin/activate && export $$(grep -v '^#' .env | xargs) && \
	python3 scripts/distribuidor_from_csv.py "$(CSV)" $(if $(DRY_RUN),--dry-run,)

check-env:
	@echo "CLICKUP_TEAM=$(CLICKUP_TEAM) (lido do shell ou .env via export manual)"

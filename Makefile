COMPOSE = docker compose -f infra/docker-compose.yml
API_URL = http://127.0.0.1:8000
PIPES   = $(API_URL)/api/v1/pipelines
DB_CONT = etl_db
PSQL    = docker exec -i $(DB_CONT) psql -U etl_user -d etl_demo
BATCH ?= 100
NAME  ?= film_dim_sql
MODE ?= full
KEY  ?= updated_at

JQ := $(shell command -v jq 2>/dev/null)

JSON_FMT = $(if $(JQ),jq .,cat)

.PHONY: help up down down-v restart build ps logs \
        api-health api-list api-get api-run api-pause api-runs \
        api-create-sql-film-dim api-create-python-film-dim \
        db-counts db-reset-demo

help:
	@echo ""
	@echo "ETL commands:"
	@echo "  make up / down / down-v / restart / build / ps / logs"
	@echo ""
	@echo "API:"
	@echo "  make api-list"
	@echo "  make api-get ID=..."
	@echo "  make api-run ID=..."
	@echo "  make api-pause ID=..."
	@echo "  make api-runs ID=..."
	@echo ""
	@echo "Create pipelines:"
	@echo "  make api-create-sql-film-dim"
	@echo "  make api-create-python-film-dim"
	@echo ""
	@echo "DB:"
	@echo "  make db-counts"
	@echo "  make db-reset-demo"
	@echo ""

# --------------------
# Docker
# --------------------
up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

down-v:
	$(COMPOSE) down -v

restart: down up

build:
	$(COMPOSE) build

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f etl_api etl_runner

# --------------------
# API
# --------------------
api-health:
	curl -s $(API_URL)/health || true

api-list:
	curl -s $(PIPES)/ | $(JSON_FMT)

api-get:
	@test -n "$(ID)" || (echo "Usage: make api-get ID=<uuid>" && exit 1)
	curl -s $(PIPES)/$(ID) | $(JSON_FMT)

api-run:
	@test -n "$(ID)" || (echo "Usage: make api-run ID=<uuid>" && exit 1)
	curl -s -X POST $(PIPES)/$(ID)/run | $(JSON_FMT)

api-pause:
	@test -n "$(ID)" || (echo "Usage: make api-pause ID=<uuid>" && exit 1)
	curl -s -X POST $(PIPES)/$(ID)/pause | $(JSON_FMT)

api-runs:
	@test -n "$(ID)" || (echo "Usage: make api-runs ID=<uuid>" && exit 1)
	curl -s "$(PIPES)/$(ID)/runs?limit=50" | $(JSON_FMT)

# --------------------
# Create pipelines
# --------------------
api-create-sql-film-dim:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)\",\
\"description\":\"Demo SQL pipeline\",\
\"type\":\"SQL\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"analytics.film_dim\",\
\"source_query\":\"SELECT id AS film_id, title, rating FROM content.film_work\"}" \
	| $(JSON_FMT)

api-create-sql-film-dim-inc:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)\",\"description\":\"Incremental SQL pipeline\",\"type\":\"SQL\",\"mode\":\"incremental\",\"enabled\":true,\"batch_size\":$(BATCH),\"incremental_key\":\"updated_at\",\"target_table\":\"analytics.film_dim\",\"source_query\":\"SELECT id AS film_id, title, rating, updated_at FROM content.film_work\"}" | $(JSON_FMT)

api-create-python-film-dim:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"film_dim_python\",\
\"description\":\"Demo PYTHON pipeline\",\
\"type\":\"PYTHON\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"analytics.film_dim\",\
\"python_module\":\"src.pipelines.python_demo.demo_film_dim\",\
\"source_query\":\"SELECT id AS film_id, title, rating FROM content.film_work\"}" \
	| $(JSON_FMT)
# --------------------
# DB helpers
# --------------------
db-counts:
	@$(PSQL) -c "select 'analytics.film_dim' as table, count(*) from analytics.film_dim;"
	@$(PSQL) -c "select 'analytics.film_rating_agg' as table, count(*) from analytics.film_rating_agg;"
	@$(PSQL) -c "select 'etl.etl_runs' as table, count(*) from etl.etl_runs;"
	@$(PSQL) -c "select 'etl.etl_state' as table, count(*) from etl.etl_state;"

db-reset-demo:
	@$(PSQL) -c "TRUNCATE analytics.film_dim RESTART IDENTITY;"
	@$(PSQL) -c "TRUNCATE analytics.film_rating_agg RESTART IDENTITY;"
	@$(PSQL) -c "TRUNCATE etl.etl_runs RESTART IDENTITY;"
	@$(PSQL) -c "TRUNCATE etl.etl_state RESTART IDENTITY;"

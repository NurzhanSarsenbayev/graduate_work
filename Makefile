COMPOSE = docker compose -f infra/docker-compose.yml
API_URL = http://127.0.0.1:8000
PIPES   = $(API_URL)/api/v1/pipelines
DB_CONT = etl_db
PSQL = docker exec -i $(DB_CONT) psql -U etl_user -d etl_demo
JQ := $(shell command -v jq 2>/dev/null)

define PRINT_JSON
	@if [ -n "$(JQ)" ]; then jq .; else cat; fi
endef

.PHONY: help up down restart build logs ps api-health api-list api-get api-create api-run api-pause api-runs demo

help:
	@echo ""
	@echo "ETL demo commands:"
	@echo "  make up           - start stack"
	@echo "  make down         - stop stack"
	@echo "  make restart      - restart stack"
	@echo "  make build        - rebuild images"
	@echo "  make ps           - show containers"
	@echo "  make logs         - tail logs (api+runner)"
	@echo ""
	@echo "API:"
	@echo "  make api-list      - list pipelines"
	@echo "  make api-get ID=.. - get pipeline"
	@echo "  make api-create    - create demo pipeline (film_dim_full_v2)"
	@echo "  make api-run ID=.. - set pipeline RUNNING"
	@echo "  make api-pause ID=.. - set pipeline PAUSED"
	@echo "  make api-runs ID=..  - list runs"
	@echo ""
	@echo "Demo:"
	@echo "  make demo ID=..   - run full demo flow"
	@echo ""

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

api-list:
	curl -s $(PIPES)/

api-get:
	@test -n "$(ID)" || (echo "Usage: make api-get ID=<pipeline_uuid>" && exit 1)
	curl -s $(PIPES)/$(ID)

api-create:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d '{"name":"film_dim_full_v2","description":"Demo pipeline","type":"SQL","mode":"full","enabled":true,"batch_size":100,"target_table":"analytics.film_dim","source_query":"SELECT id as film_id, title, rating FROM content.film_work"}' \


api-run:
	@test -n "$(ID)" || (echo "Usage: make api-run ID=<pipeline_uuid>" && exit 1)
	curl -s -X POST $(PIPES)/$(ID)/run

api-pause:
	@test -n "$(ID)" || (echo "Usage: make api-pause ID=<pipeline_uuid>" && exit 1)
	curl -s -X POST $(PIPES)/$(ID)/pause

api-runs:
	@test -n "$(ID)" || (echo "Usage: make api-runs ID=<pipeline_uuid>" && exit 1)
	curl -s "$(PIPES)/$(ID)/runs?limit=50"

db-counts:
	@$(PSQL) -c "select 'analytics.film_dim' as table, count(*) from analytics.film_dim;"
	@$(PSQL) -c "select 'analytics.film_rating_agg' as table, count(*) from analytics.film_rating_agg;"
	@$(PSQL) -c "select 'etl.etl_runs' as table, count(*) from etl.etl_runs;"
	@$(PSQL) -c "select 'etl.etl_state' as table, count(*) from etl.etl_state;"

db-reset-demo:
	@$(PSQL) -c "TRUNCATE TABLE analytics.film_dim RESTART IDENTITY;"
	@$(PSQL) -c "TRUNCATE TABLE analytics.film_rating_agg RESTART IDENTITY;"
	@$(PSQL) -c "TRUNCATE TABLE etl.etl_runs RESTART IDENTITY;"
	@$(PSQL) -c "TRUNCATE TABLE etl.etl_state RESTART IDENTITY;"

demo:
	@test -n "$(ID)" || (echo "Usage: make demo ID=<pipeline_uuid>" && exit 1)
	@echo "1) Get pipeline"
	@$(MAKE) api-get ID=$(ID)
	@echo "2) Run pipeline"
	@$(MAKE) api-run ID=$(ID)
	@echo "3) Show runner logs (CTRL+C to stop tail)"
	@$(COMPOSE) logs -f --tail=50 etl_runner
	@echo "4) Show runs"
	@$(MAKE) api-runs ID=$(ID)

COMPOSE = docker compose -f infra/docker-compose.yml
API_URL = http://127.0.0.1:8000
PIPES   = $(API_URL)/api/v1/pipelines
DB_CONT = infra-etl_db-1
PSQL    = docker exec -i $(DB_CONT) psql -U etl_user -d etl_demo
BATCH ?= 100
NAME  ?= film_dim_sql
MODE ?= full
KEY  ?= updated_at
SLEEP ?= 0.2     # секунды pg_sleep на строку
DELAY ?= 1       # задержка перед pause
DT    ?= 0.2     # интервал опроса watch
N     ?= 50      # число итераций watch

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
	@echo "Test helpers:"
	@echo "  make api-create-sql-film-dim-slow NAME=... BATCH=2 SLEEP=0.2"
	@echo "  make api-run-and-pause ID=... DELAY=1"
	@echo "  make api-watch-status ID=... N=50 DT=0.2"
	@echo "  make api-runs-delta2 ID=..."
	@echo "  make db-pipe ID=..."
	@echo "  make db-last-run ID=..."


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
	$(COMPOSE) logs -f etl_api etl_runner etl_db

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

api-run-and-pause:
	@test -n "$(ID)" || (echo "Usage: make api-run-and-pause ID=<uuid> [DELAY=1]" && exit 1)
	@curl -s -X POST $(PIPES)/$(ID)/run | $(JSON_FMT) >/dev/null
	@sleep $(DELAY)
	@curl -s -X POST $(PIPES)/$(ID)/pause | $(JSON_FMT)

api-watch-status:
	@test -n "$(ID)" || (echo "Usage: make api-watch-status ID=<uuid> [N=50 DT=0.2]" && exit 1)
	@for i in $$(seq 1 $(N)); do \
	  curl -s $(PIPES)/$(ID) | jq '{id,name,status}'; \
	  sleep $(DT); \
	done

api-run-parallel2:
	@test -n "$(ID)" || (echo "Usage: make api-run-parallel2 ID=<uuid>" && exit 1)
	@( curl -s -X POST $(PIPES)/$(ID)/run >/dev/null & \
	   curl -s -X POST $(PIPES)/$(ID)/run >/dev/null & \
	   wait )
	@echo "done"

api-runs-delta2:
	@test -n "$(ID)" || (echo "Usage: make api-runs-delta2 ID=<uuid>" && exit 1)
	@BEFORE=$$(curl -s "$(PIPES)/$(ID)/runs?limit=500" | jq 'length'); \
	( curl -s -X POST $(PIPES)/$(ID)/run >/dev/null & curl -s -X POST $(PIPES)/$(ID)/run >/dev/null & wait ); \
	AFTER=$$(curl -s "$(PIPES)/$(ID)/runs?limit=500" | jq 'length'); \
	echo "before=$$BEFORE after=$$AFTER delta=$$((AFTER-BEFORE))"

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

api-create-sql-film-dim-slow:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)\",\
\"description\":\"Slow SQL pipeline (sleep per row)\",\
\"type\":\"SQL\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"analytics.film_dim\",\
\"source_query\":\"SELECT id AS film_id, title, rating FROM content.film_work CROSS JOIN LATERAL (SELECT pg_sleep($(SLEEP))) s\"}" \
	| $(JSON_FMT)

api-create-sql-film-dim-inc:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)_inc\",\"description\":\"Incremental SQL pipeline\",\"type\":\"SQL\",\"mode\":\"incremental\",\"enabled\":true,\"batch_size\":$(BATCH),\"incremental_key\":\"updated_at\",\"target_table\":\"analytics.film_dim\",\"source_query\":\"SELECT id AS film_id, title, rating, updated_at FROM content.film_work\"}" | $(JSON_FMT)

api-create-sql-film-dim-inc-slow:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)_inc_slow\",\
\"description\":\"Slow incremental SQL pipeline (sleep per row)\",\
\"type\":\"SQL\",\
\"mode\":\"incremental\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"incremental_key\":\"$(KEY)\",\
\"target_table\":\"analytics.film_dim\",\
\"source_query\":\"SELECT id AS film_id, title, rating, updated_at FROM content.film_work CROSS JOIN LATERAL (SELECT pg_sleep($(SLEEP))) s\"}" \
	| $(JSON_FMT)

api-create-python-film-dim:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)\",\
\"description\":\"Demo PYTHON pipeline\",\
\"type\":\"PYTHON\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"analytics.film_dim\",\
\"python_module\":\"src.pipelines.python_demo.demo_film_dim\",\
\"source_query\":\"SELECT id AS film_id, title, rating FROM content.film_work\"}" \
	| $(JSON_FMT)

api-create-sql-film-rating-agg:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)\",\
\"description\":\"Demo rating aggregation\",\
\"type\":\"SQL\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"analytics.film_rating_agg\",\
\"source_query\":\"SELECT r.film_id AS film_id, AVG(r.rating)::float8 AS avg_rating, COUNT(*)::int AS rating_count FROM ugc.ratings r GROUP BY r.film_id\"}" \
	| $(JSON_FMT)

api-create-sql-film-rating-agg-slow:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)\",\
\"description\":\"Slow rating aggregation (sleep per row)\",\
\"type\":\"SQL\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"analytics.film_rating_agg\",\
\"source_query\":\"SELECT * FROM (SELECT r.film_id AS film_id, AVG(r.rating)::float8 AS avg_rating, COUNT(*)::int AS rating_count FROM ugc.ratings r GROUP BY r.film_id) q CROSS JOIN LATERAL (SELECT pg_sleep($(SLEEP))) s\"}" \
	| $(JSON_FMT)

api-create-es-film-dim:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"film_dim_es\",\
\"description\":\"Demo ES sink\",\
\"type\":\"ES\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"es:film_dim\",\
\"source_query\":\"SELECT id AS film_id, title, rating FROM content.film_work\"}" \
	| $(JSON_FMT)

api-create-es-film-rating-agg:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)\",\
\"description\":\"Demo rating aggregation -> ES\",\
\"type\":\"ES\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"es:film_rating_agg\",\
\"source_query\":\"SELECT r.film_id AS film_id, AVG(r.rating)::float8 AS avg_rating, COUNT(*)::int AS rating_count FROM ugc.ratings r GROUP BY r.film_id\"}" \
	| $(JSON_FMT)

api-create-es-film-rating-agg-slow:
	curl -s -X POST $(PIPES)/ \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(NAME)\",\
\"description\":\"Slow rating aggregation -> ES (sleep per row)\",\
\"type\":\"ES\",\
\"mode\":\"full\",\
\"enabled\":true,\
\"batch_size\":$(BATCH),\
\"target_table\":\"es:film_rating_agg\",\
\"source_query\":\"SELECT * FROM (SELECT r.film_id AS film_id, AVG(r.rating)::float8 AS avg_rating, COUNT(*)::int AS rating_count FROM ugc.ratings r GROUP BY r.film_id) q CROSS JOIN LATERAL (SELECT pg_sleep($(SLEEP))) s\"}" \
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

db-pipe:
	@test -n "$(ID)" || (echo "Usage: make db-pipe ID=<uuid>" && exit 1)
	@$(PSQL) -c "SELECT id, name, status, updated_at FROM etl.etl_pipelines WHERE id='$(ID)';"

db-last-run:
	@test -n "$(ID)" || (echo "Usage: make db-last-run ID=<uuid>" && exit 1)
	@$(PSQL) -c "SELECT id, status, started_at, finished_at, rows_read, rows_written FROM etl.etl_runs WHERE pipeline_id='$(ID)' ORDER BY started_at DESC LIMIT 1;"

db-hide-film-dim:
	@$(PSQL) -c "ALTER TABLE analytics.film_dim RENAME TO film_dim__tmp;"

db-unhide-film-dim:
	@$(PSQL) -c "ALTER TABLE analytics.film_dim__tmp RENAME TO film_dim;"

logs-runner:
	$(COMPOSE) logs -f --tail 200 etl_runner

api-get-brief:
	@test -n "$(ID)" || (echo "Usage: make api-get-brief ID=<uuid>" && exit 1)
	@curl -s $(PIPES)/$(ID) | jq '{id,name,status,mode,type,batch_size,target_table}'

test-retry-flip-film-dim:
	@test -n "$(ID)" || (echo "Usage: make test-retry-flip-film-dim ID=<uuid>" && exit 1)
	@$(MAKE) api-run ID=$(ID) >/dev/null
	@sleep 0.5
	@$(MAKE) db-hide-film-dim
	@sleep 2
	@$(MAKE) db-unhide-film-dim
	@echo "Now watch logs: make logs-runner"

db-inc-state:
	@test -n "$(ID)" || (echo "Usage: make db-inc-state ID=<uuid>" && exit 1)
	@$(PSQL) -c "SELECT pipeline_id, last_processed_value, last_processed_id FROM etl.etl_state WHERE pipeline_id='$(ID)';"

db-touch-filmwork-one:
	@$(PSQL) -c "UPDATE content.film_work SET updated_at = NOW() WHERE id = (SELECT id FROM content.film_work ORDER BY updated_at NULLS FIRST, id LIMIT 1);"
	@echo "touched one film_work.updated_at = NOW()"
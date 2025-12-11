PROJECT_NAME=etl_diploma

.PHONY: up down logs api-shell

up:
\tcd infra && docker compose up -d --build

down:
\tcd infra && docker compose down -v

logs:
\tcd infra && docker compose logs -f

api-shell:
\tdocker exec -it etl_api bash


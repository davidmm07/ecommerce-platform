.DEFAULT_GOAL := help
SHELL := /bin/bash

-include .env
export

POSTGRES_USER ?= ecommerce
POSTGRES_DB ?= ecommerce
POSTGRES_PORT ?= 5432
LOCAL_DATABASE_URL = postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@127.0.0.1:$(POSTGRES_PORT)/$(POSTGRES_DB)

.PHONY: help env up seed down logs ps install dev-db dev-api dev-web lint typecheck test check clean

help:
	@printf '  \033[36m%-10s\033[0m %s\n' 'help' 'Show the available commands'
	@printf '  \033[36m%-10s\033[0m %s\n' 'env' 'Create .env with a generated database password'
	@printf '  \033[36m%-10s\033[0m %s\n' 'up' 'Build and start the whole stack with Docker Compose'
	@printf '  \033[36m%-10s\033[0m %s\n' 'seed' 'Import the sample CSV into the running stack'
	@printf '  \033[36m%-10s\033[0m %s\n' 'down' 'Stop the stack and keep the data volume'
	@printf '  \033[36m%-10s\033[0m %s\n' 'logs' 'Follow the logs of every service'
	@printf '  \033[36m%-10s\033[0m %s\n' 'ps' 'Show the status of the services'
	@printf '  \033[36m%-10s\033[0m %s\n' 'install' 'Install backend and frontend dependencies for local development'
	@printf '  \033[36m%-10s\033[0m %s\n' 'dev-db' 'Start only PostgreSQL for local development'
	@printf '  \033[36m%-10s\033[0m %s\n' 'dev-api' 'Run migrations and the API with auto reload on port 8000'
	@printf '  \033[36m%-10s\033[0m %s\n' 'dev-web' 'Run the Vite dev server on port 5173 with the API proxy'
	@printf '  \033[36m%-10s\033[0m %s\n' 'lint' 'Lint and check formatting of both apps'
	@printf '  \033[36m%-10s\033[0m %s\n' 'typecheck' 'Static type checks and architecture contracts'
	@printf '  \033[36m%-10s\033[0m %s\n' 'test' 'Run all test suites, the backend ones start PostgreSQL with Testcontainers'
	@printf '  \033[36m%-10s\033[0m %s\n' 'check' 'Everything CI runs'
	@printf '  \033[36m%-10s\033[0m %s\n' 'clean' 'Stop the stack and delete the database volume'

env: .env

.env:
	@cp .env.example .env
	@python3 -c "import pathlib, secrets; p = pathlib.Path('.env'); p.write_text(p.read_text().replace('POSTGRES_PASSWORD=', 'POSTGRES_PASSWORD=' + secrets.token_hex(16), 1))"
	@echo "Created .env with a generated POSTGRES_PASSWORD (git ignored)."

up: .env
	docker compose up --build -d
	@echo "Web: http://localhost:$${WEB_PORT:-8080}  API docs: http://localhost:$${API_PORT:-8000}/docs"

seed: .env
	docker compose --profile seed run --rm seed

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

install:
	cd backend && uv sync
	cd frontend && npm ci

dev-db: .env
	docker compose up -d db

dev-api: .env
	cd backend && APP_DATABASE_URL="$(LOCAL_DATABASE_URL)" APP_LOG_FORMAT=text uv run alembic upgrade head
	cd backend && APP_DATABASE_URL="$(LOCAL_DATABASE_URL)" APP_LOG_FORMAT=text APP_MEDIA_SERVE=true uv run uvicorn ecommerce.presentation.api.app:create_app --factory --reload

dev-web:
	cd frontend && npm run dev

lint:
	cd backend && uv run ruff check src tests migrations && uv run ruff format --check src tests migrations
	cd frontend && npm run lint && npm run format:check

typecheck:
	cd backend && uv run mypy && uv run lint-imports
	cd frontend && npm run typecheck

test:
	cd backend && uv run pytest --cov
	cd frontend && npm test

check: lint typecheck test

clean:
	docker compose down -v

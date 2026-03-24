.PHONY: up down build logs shell-api shell-worker migrate seed-policies help

help:
	@echo "Enterprise RAG Assistant — Make commands"
	@echo ""
	@echo "  make up            Start all services (docker compose up)"
	@echo "  make down          Stop all services"
	@echo "  make build         Rebuild all Docker images"
	@echo "  make logs          Tail logs for all services"
	@echo "  make logs-api      Tail API logs only"
	@echo "  make logs-worker   Tail worker logs only"
	@echo "  make shell-api     Open a shell in the API container"
	@echo "  make shell-worker  Open a shell in the worker container"
	@echo "  make migrate       Run Alembic migrations"
	@echo "  make seed-policies Seed default policy rules via API"
	@echo "  make scrape-shopify  Trigger Shopify help center scrape"
	@echo "  make test          Run eval suite"

up:
	cp -n .env.example .env || true
	docker compose up -d
	@echo ""
	@echo "✅ Services started:"
	@echo "   API:     http://localhost:8000"
	@echo "   Docs:    http://localhost:8000/docs"
	@echo "   Console: http://localhost:8501"

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker bash

migrate:
	docker compose exec api alembic upgrade head

seed-policies:
	@echo "Seeding default policy rules..."
	@curl -s -X POST http://localhost:8000/policies/ \
	  -H "X-API-Key: dev-api-key-change-in-prod" \
	  -H "Content-Type: application/json" \
	  -d '{"name":"default_shopify_policies","description":"Default Shopify support guardrails","rule_yaml":"$(shell cat prompts/policies/default.yml | python3 -c \"import sys,json; print(json.dumps(sys.stdin.read()))\")","is_enabled":true}' \
	  | python3 -m json.tool
	@echo "Done"

scrape-shopify:
	@echo "Triggering Shopify Help Center scrape (100 pages)..."
	@curl -s -X POST http://localhost:8000/kb/scrape-shopify \
	  -H "X-API-Key: dev-api-key-change-in-prod" \
	  -H "Content-Type: application/json" \
	  -d '{"max_pages":100,"sections":["/en/manual"]}' \
	  | python3 -m json.tool

test-agent:
	@echo "Running a test agent call..."
	@curl -s -X POST http://localhost:8000/agent/run \
	  -H "X-API-Key: dev-api-key-change-in-prod" \
	  -H "Content-Type: application/json" \
	  -d '{"ticket":{"id":"test-001","channel":"chat","customer_message":"How do I process a refund for a customer?"},"kb_filters":{"product":"orders"},"agent_name":"support_ops"}' \
	  | python3 -m json.tool

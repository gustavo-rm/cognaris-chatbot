# Onboarding Chatbot — ITS

Conversational onboarding service that collects student data and produces an
`OptimizationRequest` for the downstream genetic-algorithm optimizer.

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000
Docs: http://localhost:8000/docs
Health: http://localhost:8000/api/v1/health/live

## Local development without Docker

```bash
make install
# Start Postgres + Redis (Docker or local)
make migrate
make dev
make test
```

## Project layout

- `app/api` — FastAPI routers, request/response schemas, error handlers.
- `app/core` — Configuration, logging, exceptions, cross-cutting concerns.
- `app/domain` — Domain entities, value objects, business rules (added Phase 2+).
- `app/infrastructure` — DB, cache, external clients.
- `alembic` — Database migrations.

## Roadmap

This repository is built phase by phase. Phase 1 ships the bootstrap;
subsequent phases add session management, workflow orchestration, LLM
integration, extraction, validation, and final export.
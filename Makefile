.PHONY: install run dev test lint format migrate makemigration up down logs

install:
	pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	pytest -v --cov=app --cov-report=term-missing

lint:
	ruff check app
	mypy app

format:
	ruff check --fix app
	ruff format app

migrate:
	alembic upgrade head

makemigration:
	@read -p "Message: " msg; alembic revision --autogenerate -m "$$msg"

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f app
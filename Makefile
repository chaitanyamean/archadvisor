.PHONY: setup dev test lint docker-up docker-down clean

# ── Development ──

setup:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cp .env.example .env
	@echo "✅ Setup complete. Add your API keys to .env"

dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-redis:
	docker run -d --name archadvisor-redis -p 6378:6379 redis:7-alpine

test:
	cd backend && python -m pytest tests/ -v --tb=short

lint:
	cd backend && ruff check . && ruff format --check .

format:
	cd backend && ruff format .

# ── Docker ──

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend

# ── Production ──

deploy:
	docker compose -f docker-compose.yml up --build -d
	@echo "✅ Deployed. API at http://localhost:8000/docs"

# ── Cleanup ──

clean:
	docker compose down -v
	rm -rf backend/.venv backend/__pycache__ backend/data
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned up"

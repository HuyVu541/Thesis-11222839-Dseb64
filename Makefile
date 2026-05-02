.PHONY: help install setup run run-prod test test-unit test-integration lint format clean reset-db logs

help:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  AI Memory Backend - Development Commands"
	@echo "═══════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup          - Initial project setup (recommended for first time)"
	@echo "  make install        - Install Python dependencies"
	@echo ""
	@echo "Running:"
	@echo "  make run            - Run development server (auto-reload)"
	@echo "  make run-prod       - Run production server"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Check code quality"
	@echo "  make format         - Format code automatically"
	@echo ""
	@echo "Database:"
	@echo "  make reset-db       - Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean          - Remove cache files"
	@echo "  make logs           - Follow backend logs"
	@echo "  make help           - Show this help message"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════"

setup:
	@echo "🚀 Setting up development environment..."
	@echo ""
	@echo "1️⃣  Copying environment file..."
	@test -f .env || (cp .env.example .env && echo "✅ Created .env file")
	@test -f .env && echo "⚠️  .env already exists - skipping"
	@echo ""
	@echo "2️⃣  Starting services (PostgreSQL, Langfuse)..."
	@docker-compose up -d postgres langfuse
	@echo ""
	@echo "3️⃣  Waiting for services to be ready..."
	@sleep 5
	@echo ""
	@echo "4️⃣  Installing Python dependencies..."
	@pip install -e . > /dev/null
	@echo "✅ Dependencies installed"
	@echo ""
	@echo "════════════════════════════════════════════════════════════"
	@echo "✨ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env and add your GOOGLE_API_KEY"
	@echo "  2. Run 'make run' to start the backend"
	@echo "  3. Access API at http://localhost:8000"
	@echo "  4. Access Langfuse at http://localhost:3000"
	@echo "════════════════════════════════════════════════════════════"

install:
	@echo "📦 Installing dependencies..."
	pip install -e .
	@echo "✅ Done"

run:
	@echo "🏃 Starting development server (auto-reload enabled)..."
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	@echo "🚀 Starting production server..."
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

test:
	@echo "🧪 Running all tests..."
	pytest tests/ -v

test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/unit/ -v

test-integration:
	@echo "🧪 Running integration tests..."
	pytest tests/integration/ -v

lint:
	@echo "🔍 Checking code quality..."
	@echo "Running ruff..."
	ruff check src/
	@echo ""
	@echo "Running mypy..."
	mypy src/ || true
	@echo "✅ Lint check complete"

format:
	@echo "✨ Formatting code..."
	ruff format src/
	ruff check --fix src/ || true
	@echo "✅ Code formatted"

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"

reset-db:
	@echo "⚠️  WARNING: This will delete all data!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "🗑️  Stopping and removing database..."
	docker-compose down -v
	@echo "🔄 Starting fresh database..."
	docker-compose up -d postgres
	@sleep 3
	@echo "✅ Database reset complete"

logs:
	@echo "📋 Following backend logs (Ctrl+C to stop)..."
	docker-compose logs -f backend
#!/bin/bash
# reset_and_seed.sh — Wipe all memory and re-seed prompts + sample data.
# Usage: bash scripts/reset_and_seed.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== 1. Ensuring services are running ==="
docker compose up -d
echo "Waiting for services to be healthy..."
sleep 10

echo ""
echo "=== 2. Clearing all memory ==="
echo "DELETE" | docker compose exec -T backend python src/clear_all_memory.py

echo ""
echo "=== 3. Restarting backend ==="
docker compose restart backend
echo "Waiting for backend to start..."
sleep 10

echo ""
echo "=== 4. Seeding system prompts ==="
docker compose exec -T postgres psql -U user -d langgraph < scripts/seed_prompt.sql

echo ""
echo "=== 5. Seeding sample data ==="
docker compose exec -T postgres psql -U user -d langgraph < scripts/seed_sample_data.sql

echo ""
echo "=== 6. Health check ==="
for i in 1 2 3 4 5; do
    if curl -s http://localhost:8000/sessions > /dev/null 2>&1; then
        echo "✅ Backend is healthy"
        break
    fi
    echo "  Waiting... ($i/5)"
    sleep 3
done

echo ""
echo "✅ Reset complete. Ready for testing."
echo ""
echo "Next steps:"
echo "  Generate distractors:  docker compose exec -T backend python scripts/generate_distractors.py"
echo "  Run eval (SAM):        MEMORY_MODE=sam pytest tests/test_e2e_memory.py -v --tb=short -s"
echo "  Run eval (RAG):        MEMORY_MODE=rag pytest tests/test_e2e_memory.py -v --tb=short -s"

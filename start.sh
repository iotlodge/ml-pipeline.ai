#!/usr/bin/env bash
# Start the ML Pipeline stack (backend + UI)
cd "$(dirname "$0")/ml-pipeline-agent" || exit 1
docker compose up --build -d
echo ""
echo "Backend:  http://localhost:8000"
echo "UI:       http://localhost:3000"
echo "API docs: http://localhost:8000/docs"

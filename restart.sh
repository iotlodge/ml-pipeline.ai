#!/usr/bin/env bash
# Rebuild and restart the ML Pipeline stack
cd "$(dirname "$0")/ml-pipeline-agent" || exit 1
docker compose down
docker compose up --build -d
echo ""
echo "Backend:  http://localhost:8000"
echo "UI:       http://localhost:3000"
echo "API docs: http://localhost:8000/docs"

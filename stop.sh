#!/usr/bin/env bash
# Stop the ML Pipeline stack
cd "$(dirname "$0")/ml-pipeline-agent" || exit 1
docker compose down
echo "Stack stopped."

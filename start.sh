#!/bin/bash
# Start script for Pi-Autopilot FastAPI server

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Get host and port from environment or use defaults
HOST=${APP_HOST:-0.0.0.0}
PORT=${APP_PORT:-8000}

echo "Starting Pi-Autopilot on $HOST:$PORT"
echo "====================================="

# Start uvicorn server
uvicorn main:app --host $HOST --port $PORT --reload

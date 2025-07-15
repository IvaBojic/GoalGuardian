#!/bin/bash

LOG_DIR="/app/logs"
mkdir -p "$LOG_DIR"

# Start Uvicorn with YAML-based log config
uvicorn app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-config /app/uvicorn_log_config.yaml

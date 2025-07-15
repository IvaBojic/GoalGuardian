#!/bin/bash

LOG_DIR="/app/logs"
mkdir -p "$LOG_DIR"

# Start FastAPI using log config
uvicorn app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-config /app/uvicorn_log_config.yaml &

# Start Streamlit
streamlit run streamlit_app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 | tee -a "$LOG_DIR/print.log"

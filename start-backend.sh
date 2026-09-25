#!/bin/sh
export TALEMATE_DEBUG=1
uv run --offline --no-sync src/talemate/server/run.py runserver --host 127.0.0.1 --port "${TALEMATE_BACKEND_PORT:-5050}" --backend-only
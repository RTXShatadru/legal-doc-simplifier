#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
(cd frontend-react && npm ci && npm run build)
echo 'Open http://127.0.0.1:8000 after startup. Press Ctrl+C to stop.'
exec .venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000

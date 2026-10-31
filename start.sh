#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) PYTHON=python; VENV_PY=.venv/Scripts/python.exe ;;
  *) PYTHON=python3; VENV_PY=.venv/bin/python ;;
esac
[ -f "$VENV_PY" ] || "$PYTHON" -m venv .venv
[ -f .env ] || cp .env.example .env
"$VENV_PY" backend/prepare_env.py
"$VENV_PY" -m pip install -r backend/requirements.lock.txt
(cd frontend-react && npm ci && npm run build)
echo 'Open http://127.0.0.1:8002 after startup. Press Ctrl+C to stop.'
exec "$VENV_PY" -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8002

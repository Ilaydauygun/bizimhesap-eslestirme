#!/usr/bin/env bash
cd "$(dirname "$0")"
(cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000) &
(cd frontend && npm run dev -- --host 127.0.0.1) &
wait

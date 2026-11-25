#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
[ -f bizimhesap.db ] || .venv/bin/python -m app.seed_data.seed
cd ../frontend && npm install --silent
echo "Kurulum tamam. ./calistir.sh ile başlatın."

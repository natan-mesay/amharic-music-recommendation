#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "⚡ Starting Acoustic Vault Music Discovery Recommender"
echo "=========================================================="

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

echo "🚀 Starting FastAPI server on http://localhost:8000 ..."
PYTHONPATH=. ./venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

#!/usr/bin/env bash
# PathForge — one-shot dev starter (macOS / Linux)
set -e

echo "Starting PathForge..."
echo ""
echo "[1/2] Make sure Ollama is running:"
echo "      ollama serve   (in another terminal)"
echo "      ollama pull llama3.2   (one-time)"
echo ""

cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

if [ ! -f ".env" ]; then
    echo "Copying .env.example to .env..."
    cp .env.example .env
fi

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "Starting backend on http://localhost:8000"
echo "Open frontend with VS Code Live Server on frontend/index.html"
echo ""

uvicorn app.main:app --reload --port 8000

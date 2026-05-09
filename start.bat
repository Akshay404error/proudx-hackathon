@echo off
REM PathForge — one-shot dev starter (Windows)
echo Starting PathForge...
echo.
echo [1/2] Make sure Ollama is running:
echo       ollama serve   (in another terminal)
echo       ollama pull llama3.2   (one-time)
echo.

cd backend
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
if not exist .env (
    echo Copying .env.example to .env...
    copy .env.example .env
)
echo Installing dependencies...
pip install -q -r requirements.txt
echo.
echo Starting backend on http://localhost:8000
echo Open frontend with VS Code Live Server on frontend/index.html
echo.
uvicorn app.main:app --reload --port 8000

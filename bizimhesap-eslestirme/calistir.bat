@echo off
chcp 65001 >nul
start "Backend (http://localhost:8000/docs)" /d "%~dp0backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --port 8000"
start "Frontend (http://localhost:5173)" /d "%~dp0frontend" cmd /k "npm run dev -- --open"

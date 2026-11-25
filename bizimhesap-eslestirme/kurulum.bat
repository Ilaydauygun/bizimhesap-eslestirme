@echo off
chcp 65001 >nul
echo === Backend kurulumu ===
cd /d "%~dp0backend"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if not exist bizimhesap.db python -m app.seed_data.seed
echo === Frontend kurulumu ===
cd /d "%~dp0frontend"
call npm install
echo.
echo Kurulum tamam. Baslatmak icin calistir.bat dosyasini calistirin.
pause

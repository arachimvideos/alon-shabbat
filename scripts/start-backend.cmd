@echo off
setlocal
title Articles Backend

cd /d "%~dp0..\backend"

if not exist ".venv\Scripts\python.exe" (
  echo Python environment was not found.
  echo Please run start-backend.ps1 once, or ask Codex to rebuild the environment.
  pause
  exit /b 1
)

echo Starting the articles data server...
echo.
echo Keep this window open while using the site.
echo Backend address: http://127.0.0.1:8000
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo The backend stopped. If you see an error above, send it to Codex.
pause

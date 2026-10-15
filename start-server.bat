@echo off
REM Basket Campaign Manager - start backend + frontend dev servers
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Expected: %CD%\.venv\Scripts\python.exe
  echo Create it with: python -m venv .venv
  pause
  exit /b 1
)

if not exist "backend\manage.py" (
  echo [ERROR] backend\manage.py not found in %CD%\backend
  pause
  exit /b 1
)

if not exist "backend\.env" (
  if exist "backend\.env.example" (
    echo [INFO] backend\.env missing - copying from .env.example
    copy "backend\.env.example" "backend\.env" >nul
  )
)

echo [1/2] Starting Django API on http://127.0.0.1:8000 ...
start "basket-backend" cmd /k ".\.venv\Scripts\python.exe backend\manage.py migrate && .\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000"

if exist "frontend\package.json" (
  echo [2/2] Starting Vite frontend on http://127.0.0.1:5173 ...
  start "basket-frontend" /d "frontend" cmd /k "npm run dev -- --port 5173 --host 127.0.0.1"
) else (
  echo [SKIP] frontend\package.json not found, backend only.
)

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5173"
echo Done. Close the opened windows to stop the servers.

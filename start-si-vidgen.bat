@echo off
setlocal EnableExtensions

rem Start SI VidGen API + Vite UI, then open the default browser.
rem Double-click this file, or run it from a Command Prompt.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python venv not found at .venv\Scripts\python.exe
  echo Create it first with:  py -3.11 -m venv .venv
  echo Then install deps:     .\.venv\Scripts\python -m pip install -r requirements-dev.txt
  pause
  exit /b 1
)

if not exist "web\package.json" (
  echo [ERROR] web\package.json not found. Are you in the SI_VidGen repo root?
  pause
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm was not found on PATH. Install Node.js, then retry.
  pause
  exit /b 1
)

echo Starting SI VidGen API on http://127.0.0.1:8000 ...
start "SI VidGen API" cmd /k "cd /d ""%~dp0"" && set PYTHONPATH=%~dp0&& .venv\Scripts\python.exe main.py"

echo Starting SI VidGen UI on http://127.0.0.1:5173 ...
start "SI VidGen UI" cmd /k "cd /d ""%~dp0web"" && npm run dev -- --host 127.0.0.1 --port 5173"

echo Waiting for the UI to become ready...
powershell -NoProfile -Command ^
  "$deadline = (Get-Date).AddSeconds(60);" ^
  "do {" ^
  "  try {" ^
  "    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2;" ^
  "    if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 }" ^
  "  } catch {}" ^
  "  Start-Sleep -Milliseconds 500" ^
  "} while ((Get-Date) -lt $deadline);" ^
  "exit 1"

if errorlevel 1 (
  echo [WARN] UI did not respond within 60 seconds. Opening the browser anyway.
) else (
  echo UI is ready.
)

start "" "http://127.0.0.1:5173/"

echo.
echo API and UI are running in separate windows titled:
echo   - SI VidGen API
echo   - SI VidGen UI
echo Close those windows to stop the servers.
echo.
pause
endlocal

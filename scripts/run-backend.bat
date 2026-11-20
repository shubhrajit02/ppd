@echo off
rem Starts the API on http://127.0.0.1:8000. Creates .venv and installs on first run. Loads .env if present.
cd /d "%~dp0.."
if not exist .venv\Scripts\aicr-api.exe (
  py -3.11 -m venv .venv || exit /b 1
  .venv\Scripts\python.exe -m pip install -c backend/requirements-dev.lock -e "backend[web,dev]" || exit /b 1
)
if exist .env (
  for /f "usebackq eol=# tokens=1* delims==" %%a in (".env") do set "%%a=%%b"
)
.venv\Scripts\aicr-api.exe

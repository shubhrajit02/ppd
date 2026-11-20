@echo off
rem Starts the web app on http://127.0.0.1:3000. Installs dependencies on first run.
cd /d "%~dp0..\frontend"
if not exist node_modules call npm ci || exit /b 1
call npm run dev

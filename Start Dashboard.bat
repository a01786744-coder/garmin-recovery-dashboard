@echo off
title Garmin Recovery Dashboard
cd /d "%~dp0"

if not exist "node_modules\electron\dist\electron.exe" (
  echo.
  echo   First-time setup needed. In this folder, run these once:
  echo      npm install
  echo      npm --prefix frontend install
  echo.
  pause
  exit /b
)

if not exist "frontend\dist\index.html" (
  echo Preparing the dashboard for first launch, please wait...
  call npm run build:frontend
)

start "" "%~dp0node_modules\electron\dist\electron.exe" "%~dp0."
exit /b

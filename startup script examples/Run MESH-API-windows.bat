@echo off
setlocal

REM --- Always start in the folder where this .bat lives ---
cd /d "%~dp0"

REM --- Activate virtual environment if it exists ---
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

REM --- Run mesh-api ---
if exist "mesh-api.py" (
  python mesh-api.py %*
) else (
  echo [ERROR] Could not find mesh-api.py in: %cd%
  echo Available Python files:
  dir /b *.py
  pause
  exit /b 1
)

pause

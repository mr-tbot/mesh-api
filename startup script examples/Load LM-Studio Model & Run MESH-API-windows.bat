@echo off
cd /d "%USERPROFILE%\Desktop\mesh-api"  REM Your MESH-API directory

echo Unloading any previously loaded model before reloading...
lms unload <INSERT MODEL IDENTIFIER HERE>
timeout /t 2 /nobreak >nul

echo Loading defined model...
lms load <INSERT MODEL IDENTIFIER HERE>
timeout /t 5 /nobreak >nul

echo Running MESH-API...
python mesh-api.py

pause

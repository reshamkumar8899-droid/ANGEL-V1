@echo off
echo Starting Angel backend...
start /b python angel.py --overlay

:: Wait for the HTTP server to come up
timeout /t 3 /nobreak >nul

echo Launching overlay...
cd /d "%~dp0overlay"
call npx electron .

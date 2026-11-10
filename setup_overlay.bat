@echo off
echo ================================================
echo   A.N.G.E.L -- Variant I  ^|  Overlay Setup
echo ================================================
echo.

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found.
    echo Please install Node.js from https://nodejs.org/
    echo Then re-run this script.
    pause
    exit /b 1
)

echo [1/3] Installing Electron overlay dependencies...
cd /d "%~dp0overlay"
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed. Check your Node.js installation.
    pause
    exit /b 1
)
echo.

echo [2/3] Setting up Electron binary...
:: Node.js v26+ blocks postinstall scripts — approve and extract manually
call npm install-scripts approve electron >nul 2>&1

:: Check if electron.exe exists, if not extract from cache
if not exist "node_modules\electron\dist\electron.exe" (
    echo [INFO] Extracting Electron binary from cache...
    :: Try running the install script first
    node node_modules\electron\install.js >nul 2>&1
)
:: If still missing, try PowerShell extraction
if not exist "node_modules\electron\dist\electron.exe" (
    for /f "delims=" %%Z in ('dir /s /b "%LOCALAPPDATA%\electron\Cache\electron-*win32-x64.zip" 2^>nul') do (
        echo [INFO] Manually extracting from: %%Z
        powershell -NoProfile -Command "Expand-Archive -Path '%%Z' -DestinationPath '%cd%\node_modules\electron\dist' -Force"
    )
)
:: Create path.txt if missing (tells Electron module where the binary is)
if not exist "node_modules\electron\path.txt" (
    echo electron.exe> "node_modules\electron\path.txt"
)
:: Final check
if exist "node_modules\electron\dist\electron.exe" (
    echo [OK] Electron binary ready.
) else (
    echo [WARN] Could not extract Electron automatically.
    echo        Try: cd overlay ^& node node_modules\electron\install.js
)
echo.

echo [3/3] Setup complete!
echo.
echo ================================================
echo   Overlay setup done!
echo.
echo   Run: run_overlay.bat  to launch Angel as a
echo   transparent desktop overlay.
echo ================================================
pause

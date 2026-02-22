@echo off
setlocal

cd /d "%~dp0"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8501"

echo ==================================================
echo   Mobile OS Memory Management System - Launcher
echo ==================================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\activate.bat
    echo Create it first using: python -m venv .venv
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Python environment activated.
python --version
echo.

echo [INFO] Installing / verifying dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)
echo.

set "ADB_DIR=%LOCALAPPDATA%\Android\platform-tools"
if exist "%ADB_DIR%\adb.exe" (
    set "PATH=%PATH%;%ADB_DIR%"
)

where adb >nul 2>&1
if errorlevel 1 (
    echo [WARN] ADB not found on PATH. Dashboard can still run in demo mode.
) else (
    echo [INFO] Starting ADB server...
    adb start-server >nul 2>&1
    echo [INFO] Connected devices:
    adb devices
)
echo.

echo [INFO] Starting Streamlit on port %PORT% ...
echo [INFO] Open: http://localhost:%PORT%
echo.
streamlit run app.py --server.port %PORT%

endlocal

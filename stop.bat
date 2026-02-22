@echo off
title Stop Memory Manager
echo.
echo ========================================
echo   Stopping Memory Manager Dashboard
echo ========================================
echo.

:: Kill any running Streamlit processes
taskkill /F /IM streamlit.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq streamlit*" >nul 2>&1

:: Kill Python processes running streamlit
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr /i "PID"') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | findstr /i "streamlit" >nul 2>&1 && taskkill /F /PID %%a >nul 2>&1
)

echo.
echo [OK] All Streamlit processes stopped.
echo.
pause

@echo off
rem Starts AI Mod Painter. Double-click it, or run: start.bat [ROOT_FOLDER]
rem The first start prepares the Python environment with uv (https://docs.astral.sh/uv/).
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv was not found. Install it from https://docs.astral.sh/uv/ and run start.bat again.
    pause
    exit /b 20
)

uv sync --locked --quiet
if errorlevel 1 (
    echo Preparing the Python environment failed, see the messages above.
    pause
    exit /b 21
)

rem The GUI entry point has no console window; "start" detaches it so this window closes.
start "" "%~dp0.venv\Scripts\ai-mod-painter-gui.exe" %*
exit /b 0

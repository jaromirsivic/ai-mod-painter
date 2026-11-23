@echo off
rem Starts AI Mod Painter from this repository (needs uv: https://docs.astral.sh/uv/).
setlocal
where uv >nul 2>nul
if errorlevel 1 (
    echo uv was not found. Install uv, then run this launcher again. 1>&2
    exit /b 20
)
uv run --project "%~dp0.." ai-mod-painter %*
exit /b %ERRORLEVEL%

@echo off
REM ---------------------------------------------------------------------------
REM  Loto Winner - lanceur Windows (raccourci vers le script PowerShell)
REM  Usage : start.bat [-BackendPort 5000] [-FrontendPort 5173] [-SkipInstall]
REM ---------------------------------------------------------------------------
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%start.ps1"

if not exist "%PS_SCRIPT%" (
    echo Erreur : script introuvable - "%PS_SCRIPT%"
    exit /b 1
)

where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
    pwsh -NoLogo -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
) else (
    powershell -NoLogo -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
)

endlocal

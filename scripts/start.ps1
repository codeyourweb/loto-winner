#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Starts the Loto Winner application (Flask backend + React frontend) on Windows.

.DESCRIPTION
    The script prepares the environment (Python venv, npm dependencies) then
    starts both development servers in parallel. It shuts down cleanly when the
    user presses Ctrl+C.
    Compatible with Windows PowerShell 5.1 and PowerShell 7+.

.PARAMETER BackendPort
    Listen port of the Flask API (default: 5000).

.PARAMETER FrontendPort
    Port of the Vite server (default: 5173).

.PARAMETER SkipInstall
    Do not (re)install the dependencies.

.PARAMETER NoBrowser
    Do not open the browser automatically.

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 -BackendPort 5001 -FrontendPort 5174 -SkipInstall
#>

[CmdletBinding()]
param(
    [int]$BackendPort = 5000,
    [int]$FrontendPort = 5173,
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "    OK  $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "    !!  $Message" -ForegroundColor Yellow
}

function Get-NpmCommand {
    # On Windows, npm is a .cmd script; it must be invoked explicitly.
    $npmCmd = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if ($npmCmd) { return $npmCmd.Source }
    $npm = Get-Command "npm" -ErrorAction SilentlyContinue
    if ($npm) { return $npm.Source }
    return $null
}

function Wait-Endpoint([string]$Url, [int]$TimeoutSec = 45) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
            return $true
        } catch {
            Start-Sleep -Milliseconds 700
        }
    }
    return $false
}

# ---------------------------------------------------------------------------
# 1. Prerequisites
# ---------------------------------------------------------------------------
Write-Step "Verification des prerequis"

$pythonCmd = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "Python introuvable. Installez Python 3.11+ depuis https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

$npmCmd = Get-NpmCommand
if (-not $npmCmd) {
    Write-Host "npm introuvable. Installez Node.js 20+ depuis https://nodejs.org/" -ForegroundColor Red
    exit 1
}

Write-Ok "python et npm sont disponibles"

if (-not (Test-Path $BackendDir)) { throw "Dossier backend introuvable : $BackendDir" }
if (-not (Test-Path $FrontendDir)) { throw "Dossier frontend introuvable : $FrontendDir" }

# ---------------------------------------------------------------------------
# 2. Python environment (venv) + dependencies
# ---------------------------------------------------------------------------
if (-not $SkipInstall) {
    Write-Step "Preparation de l'environnement Python"

    if (-not (Test-Path $VenvPython)) {
        Write-Host "    Creation du virtualenv..."
        & $pythonCmd.Source -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "Echec de la creation du virtualenv" }
        Write-Ok "Virtualenv cree dans backend\.venv"
    } else {
        Write-Ok "Virtualenv existant reutilise"
    }

    & $VenvPython -m pip install --upgrade pip --quiet
    & $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt") --quiet
    if ($LASTEXITCODE -ne 0) { throw "Echec de l'installation des dependances Python" }
    Write-Ok "Dependances Python installees"

    Write-Step "Preparation des dependances Node"
    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Push-Location $FrontendDir
        try {
            & $npmCmd install --silent
            if ($LASTEXITCODE -ne 0) { throw "Echec de npm install" }
        } finally {
            Pop-Location
        }
    }
    Write-Ok "Dependances npm installees"
} else {
    Write-Warn "Installation ignoree (-SkipInstall)"
    if (-not (Test-Path $VenvPython)) { throw "Virtualenv absent : lancez sans -SkipInstall" }
}

# ---------------------------------------------------------------------------
# 3. Starting the servers
# ---------------------------------------------------------------------------
Write-Step "Demarrage de l'API Flask sur le port $BackendPort"

$backendProcess = Start-Process -FilePath $VenvPython `
    -ArgumentList "run.py", "--port", "$BackendPort" `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -WindowStyle Hidden

Write-Ok "Backend demarre (PID $($backendProcess.Id))"

Write-Step "Demarrage du frontend Vite sur le port $FrontendPort"

# Vite must proxy /api to the correct backend port.
$env:LOTO_BACKEND_PORT = "$BackendPort"
$frontendProcess = Start-Process -FilePath $npmCmd `
    -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort" `
    -WorkingDirectory $FrontendDir `
    -PassThru `
    -WindowStyle Hidden

Write-Ok "Frontend demarre (PID $($frontendProcess.Id))"

# ---------------------------------------------------------------------------
# 4. Wait, then open the browser
# ---------------------------------------------------------------------------
Write-Step "Attente de la disponibilite des serveurs"

$backendReady = Wait-Endpoint "http://127.0.0.1:$BackendPort/api/health"
$frontendReady = Wait-Endpoint "http://127.0.0.1:$FrontendPort/"

if ($backendReady) { Write-Ok "API prete : http://127.0.0.1:$BackendPort/api/health" }
else { Write-Warn "L'API n'a pas repondu dans le delai imparti" }

if ($frontendReady) { Write-Ok "Interface prete : http://127.0.0.1:$FrontendPort" }
else { Write-Warn "Le frontend n'a pas repondu dans le delai imparti" }

if ($frontendReady -and -not $NoBrowser) {
    Start-Process "http://127.0.0.1:$FrontendPort"
}

Write-Host ""
Write-Host "  Loto Winner est en cours d'execution." -ForegroundColor Green
Write-Host "  Interface : http://127.0.0.1:$FrontendPort"
Write-Host "  API       : http://127.0.0.1:$BackendPort"
Write-Host "  Appuyez sur Ctrl+C pour tout arreter." -ForegroundColor Yellow
Write-Host ""

# ---------------------------------------------------------------------------
# 5. Clean shutdown
# ---------------------------------------------------------------------------
try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
            Write-Warn "Un des serveurs s'est arrete : extinction de l'application."
            break
        }
    }
} finally {
    Write-Step "Arret des serveurs"
    foreach ($process in @($frontendProcess, $backendProcess)) {
        if ($process -and -not $process.HasExited) {
            try {
                # /T also kills child processes (node -> vite, python -> reloader).
                & taskkill /PID $process.Id /T /F 2>$null | Out-Null
            } catch {
                Write-Warn "Impossible d'arreter le PID $($process.Id)"
            }
        }
    }
    Write-Ok "Serveurs arretes"
}

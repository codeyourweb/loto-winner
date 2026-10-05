#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Starts the Loto Winner API in production mode on Windows (waitress server).

.DESCRIPTION
    Unlike start.ps1 (development), this script enables neither auto-reload nor
    the debugger: it serves the API through a production WSGI server.

    REQUIRED environment variables:
        LOTO_SECRET_KEY     random secret key (>= 32 characters)
        LOTO_CORS_ORIGINS   allowed origins, comma-separated

.EXAMPLE
    $env:LOTO_SECRET_KEY = (python -c "import secrets;print(secrets.token_hex(32))")
    $env:LOTO_CORS_ORIGINS = "https://loto.example"
    .\scripts\start-prod.ps1 -Port 8000
#>

[CmdletBinding()]
param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000,
    [int]$Threads = 8
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Fail([string]$Message) {
    Write-Host $Message -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==> Verification de la configuration de production" -ForegroundColor Cyan

if (-not (Test-Path $VenvPython)) {
    Fail "Virtualenv introuvable. Lancez d'abord .\scripts\start.ps1 (ou creez backend\.venv)."
}

if (-not $env:LOTO_SECRET_KEY) {
    Fail "LOTO_SECRET_KEY est requis.`n  `$env:LOTO_SECRET_KEY = (python -c ""import secrets;print(secrets.token_hex(32))"")"
}
if ($env:LOTO_SECRET_KEY.Length -lt 32) {
    Fail "LOTO_SECRET_KEY doit faire au moins 32 caracteres."
}
if (-not $env:LOTO_CORS_ORIGINS) {
    Fail "LOTO_CORS_ORIGINS est requis. Exemple :`n  `$env:LOTO_CORS_ORIGINS = ""https://loto.example"""
}

Write-Host "    Pensez a placer un reverse proxy TLS (IIS/nginx/Caddy) devant l'API." -ForegroundColor Yellow

# Checks that waitress is available.
& $VenvPython -c "import waitress" 2>$null
if ($LASTEXITCODE -ne 0) {
    Fail "waitress n'est pas installe. Executez :`n  & ""$VenvPython"" -m pip install waitress"
}

Write-Host ""
Write-Host "==> Demarrage via waitress sur $HostAddress`:$Port" -ForegroundColor Cyan
if ($env:LOTO_CORS_ORIGINS) { Write-Host "    Origines autorisees : $env:LOTO_CORS_ORIGINS" }

Push-Location $BackendDir
try {
    & $VenvPython -m waitress --host="$HostAddress" --port="$Port" --threads="$Threads" wsgi:app
} finally {
    Pop-Location
}

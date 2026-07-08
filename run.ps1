<#
.SYNOPSIS
    Sentinel launcher. Creates the virtual environment on first run, then runs
    the requested command.

.EXAMPLE
    .\run.ps1              # run the offline incident simulation
    .\run.ps1 sim -Alert 1 # run a specific sample alert
    .\run.ps1 test         # run the test suite
    .\run.ps1 server       # start the API server (http://localhost:8000/docs)
    .\run.ps1 setup        # just create the venv and install deps
#>
param(
    [ValidateSet("sim", "test", "server", "setup", "help")]
    [string]$Command = "sim",
    [int]$Alert = 0
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

Set-Location $Root

function Initialize-Venv {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "First run: creating virtual environment in .venv ..." -ForegroundColor Cyan
        python -m venv (Join-Path $Root ".venv")
        Write-Host "Installing Sentinel and dependencies ..." -ForegroundColor Cyan
        & $VenvPython -m pip install --upgrade pip --quiet
        & $VenvPython -m pip install -e ".[dev]" --quiet
        Write-Host "Environment ready." -ForegroundColor Green
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "Sentinel launcher" -ForegroundColor Green
    Write-Host "  .\run.ps1            Run the offline incident simulation (default)"
    Write-Host "  .\run.ps1 sim -Alert 1   Run a specific sample alert by index"
    Write-Host "  .\run.ps1 test           Run the pytest suite"
    Write-Host "  .\run.ps1 server         Start the API server on http://localhost:8000"
    Write-Host "  .\run.ps1 setup          Create the venv and install deps only"
    Write-Host ""
}

switch ($Command) {
    "help"   { Show-Help }
    "setup"  { Initialize-Venv }
    "test"   { Initialize-Venv; & $VenvPython -m pytest }
    "server" {
        Initialize-Venv
        Write-Host "Starting server -> http://localhost:8000/docs (Ctrl+C to stop)" -ForegroundColor Cyan
        & $VenvPython -m uvicorn sentinel.api.main:app --reload
    }
    "sim"    {
        Initialize-Venv
        & $VenvPython (Join-Path $Root "scripts\simulate.py") --alert $Alert
    }
}

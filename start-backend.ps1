# start-backend.ps1
$BackendDir = "$PSScriptRoot\backend"
$VenvPath = "$BackendDir\venv"

if (!(Test-Path $VenvPath)) {
    Write-Host "Error: Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host "Please create it first with: python -m venv venv"
    exit 1
}

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
# Activate venv
& "$VenvPath\Scripts\Activate.ps1"

Write-Host "Starting Uvicorn server..." -ForegroundColor Green
Set-Location $BackendDir
uvicorn main:app --reload

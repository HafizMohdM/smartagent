# start-frontend.ps1
$FrontendDir = "$PSScriptRoot\frontend"

if (!(Test-Path $FrontendDir)) {
    Write-Host "Error: Frontend directory not found at $FrontendDir" -ForegroundColor Red
    exit 1
}

Write-Host "Starting Vite development server..." -ForegroundColor Cyan
Set-Location $FrontendDir
npm run dev

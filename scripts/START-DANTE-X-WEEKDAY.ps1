"""Weekday shadow runner. Reuses a healthy API. Does not place orders."""
param(
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$log = Join-Path $root "data\runtime\weekday-runner.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
function Write-Heartbeat($message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $message
    Add-Content -Path $log -Value $line
    Write-Host $line
}
$health = "http://127.0.0.1:$Port/health"
try {
    $response = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 3
    if ($response.StatusCode -eq 200) {
        Write-Heartbeat "REUSE healthy API on port $Port"
        exit 0
    }
} catch {
    Write-Heartbeat "API not healthy; starting shadow engine"
}
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
$env:DANTEX_MODE = "shadow"
Write-Heartbeat "START uvicorn shadow"
$engine = Join-Path $root "services\engine"
Start-Process -FilePath $python -ArgumentList @("-m","uvicorn","dantex.api:app","--host","127.0.0.1","--port","$Port") -WorkingDirectory $engine -WindowStyle Hidden
Start-Sleep -Seconds 3
try {
    Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 5 | Out-Null
    Write-Heartbeat "STARTED"
} catch {
    Write-Heartbeat "START_FAILED"
    exit 1
}

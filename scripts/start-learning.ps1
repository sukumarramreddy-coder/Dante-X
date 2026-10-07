param(
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [Parameter(Mandatory=$true)][string]$NodePath,
    [Parameter(Mandatory=$true)][string]$DataDir,
    [string]$CredentialsFile,
    [int]$EnginePort = 8010,
    [int]$WebPort = 3010
)
$ErrorActionPreference = 'Stop'
$repoDir = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dataPath = [IO.Path]::GetFullPath($DataDir)
New-Item -ItemType Directory -Force -Path $dataPath | Out-Null
$engineHealthy = $false
try {
    $report = Invoke-RestMethod -Uri "http://127.0.0.1:$EnginePort/v1/calibration/learning" -TimeoutSec 5
    $engineHealthy = $report.version -eq 'learning-30-v1'
} catch { }
if (-not $engineHealthy) {
    if (Get-NetTCPConnection -State Listen -LocalPort $EnginePort -ErrorAction SilentlyContinue) {
        throw "Engine port $EnginePort is already used by another service."
    }
    $engineScript = Join-Path $repoDir 'scripts/run_learning.py'
    $arguments = @(('"{0}"' -f $engineScript), '--data-dir', ('"{0}"' -f $dataPath), '--port', $EnginePort)
    if ($CredentialsFile) { $arguments += @('--credentials-file', ('"{0}"' -f $CredentialsFile)) }
    $engineProcess = Start-Process -FilePath $PythonPath -ArgumentList $arguments -WorkingDirectory $repoDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataPath 'engine.log') -RedirectStandardError (Join-Path $dataPath 'engine-error.log')
    $engineProcess.Id | Set-Content -LiteralPath (Join-Path $dataPath 'engine.pid')
}
if (-not (Get-NetTCPConnection -State Listen -LocalPort $WebPort -ErrorAction SilentlyContinue)) {
    $env:DANTEX_ENGINE_URL = "http://127.0.0.1:$EnginePort"
    $webDir = Join-Path $repoDir 'apps/web'
    $next = Join-Path $webDir 'node_modules/next/dist/bin/next'
    $webProcess = Start-Process -FilePath $NodePath -ArgumentList @(('"{0}"' -f $next), 'start', '-H', '127.0.0.1', '-p', $WebPort) -WorkingDirectory $webDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataPath 'web.log') -RedirectStandardError (Join-Path $dataPath 'web-error.log')
    $webProcess.Id | Set-Content -LiteralPath (Join-Path $dataPath 'web.pid')
}
Write-Output "Local learning dashboard: http://127.0.0.1:$WebPort"
Write-Output "Persistent learning data: $dataPath"

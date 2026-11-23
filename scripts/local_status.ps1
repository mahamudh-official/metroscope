# ==============================================================================
# MetroScope — Local Status Script (PowerShell)
# Reports health, connectivity, and active configurations across all local services
# ==============================================================================
$ErrorActionPreference = 'SilentlyContinue'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PidDir = Join-Path $ProjectRoot '.pids'

function Test-PortOnline([string]$hostName, [int]$port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($hostName, $port, $null, $null)
        $wait = $iar.AsyncWaitHandle.WaitOne(1000)
        if ($wait) {
            $client.EndConnect($iar)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

Write-Host '==================================================================' -ForegroundColor Cyan
Write-Host '               METROSCOPE — LOCAL SERVICE STATUS                 ' -ForegroundColor Cyan
Write-Host '==================================================================' -ForegroundColor Cyan

# 1. PostgreSQL Check
$dbStatus = 'DOWN'
$dbColor = 'Red'
if (Test-PortOnline '127.0.0.1' 5433) {
    $dbStatus = 'ONLINE (Port 5433 - .postgres_runtime)'
    $dbColor = 'Green'
}
Write-Host "  PostgreSQL Database : $dbStatus" -ForegroundColor $dbColor

# 2. Backend Check
$beStatus = 'DOWN'
$beColor = 'Red'
$beMetrics = $null
try {
    $res = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2
    if ($res.StatusCode -eq 200) {
        $beStatus = 'HEALTHY (Port 8000)'
        $beColor = 'Green'
    }
    $metricsRes = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health/metrics' -UseBasicParsing -TimeoutSec 2
    if ($metricsRes.StatusCode -eq 200) {
        $beMetrics = $metricsRes.Content | ConvertFrom-Json
    }
} catch {}
Write-Host "  FastAPI Backend API : $beStatus" -ForegroundColor $beColor

# 3. Frontend Check
$feStatus = 'DOWN'
$feColor = 'Red'
try {
    $feRes = Invoke-WebRequest -Uri 'http://127.0.0.1:3000/' -UseBasicParsing -TimeoutSec 2
    if ($feRes.StatusCode -eq 200) {
        $feStatus = 'READY (Port 3000)'
        $feColor = 'Green'
    }
} catch {}
Write-Host "  Next.js Frontend    : $feStatus" -ForegroundColor $feColor

# 4. Worker Check
$workerStatus = 'UNKNOWN'
$workerColor = 'Yellow'
$workerPidFile = Join-Path $PidDir 'worker.pid'
if (Test-Path $workerPidFile) {
    $wId = Get-Content $workerPidFile
    $wProc = Get-Process -Id ([int]$wId) -ErrorAction SilentlyContinue
    if ($wProc) {
        $workerStatus = "RUNNING (PID: $wId)"
        $workerColor = 'Green'
    } else {
        $workerStatus = "STOPPED (Stale PID: $wId)"
        $workerColor = 'Red'
    }
} else {
    $workerStatus = 'STOPPED'
    $workerColor = 'Red'
}
Write-Host "  Background Worker   : $workerStatus" -ForegroundColor $workerColor

# 5. Operational Metrics
Write-Host '------------------------------------------------------------------' -ForegroundColor DarkGray
if ($beMetrics) {
    Write-Host "  * Database Connected    : $($beMetrics.database_connected)" -ForegroundColor Cyan
    Write-Host "  * Published Articles    : $($beMetrics.total_articles)" -ForegroundColor Cyan
    Write-Host "  * Active Subscribers    : $($beMetrics.active_subscribers)" -ForegroundColor Cyan
    Write-Host "  * Social Dry Run Mode   : $($beMetrics.social_dry_run)" -ForegroundColor Green
    Write-Host "  * Email Dry Run Mode    : $($beMetrics.email_dry_run)" -ForegroundColor Green
} else {
    Write-Host '  * Metrics unavailable (start backend to view live metrics).' -ForegroundColor DarkGray
}

Write-Host '==================================================================' -ForegroundColor Cyan
Write-Host ''

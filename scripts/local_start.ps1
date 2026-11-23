# ==============================================================================
# MetroScope — Local One-Command Startup Script (PowerShell)
# Starts: PostgreSQL (.postgres_runtime), FastAPI Backend, APScheduler Worker, Next.js Frontend
# ==============================================================================
[CmdletBinding()]
param(
    [switch]$Docker,
    [switch]$KeepAlive
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

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
Write-Host '               METROSCOPE — LOCAL STARTUP ENGINE                 ' -ForegroundColor Cyan
Write-Host '==================================================================' -ForegroundColor Cyan

# 1. Environment Verification
$EnvFile = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $EnvFile)) {
    Write-Host '[CONFIG] .env not found. Creating from .env.example...' -ForegroundColor Yellow
    Copy-Item (Join-Path $ProjectRoot '.env.example') $EnvFile
}
Write-Host "[CONFIG] Environment file verified: $EnvFile" -ForegroundColor Green

# Create log and pid directories
$LogDir = Join-Path $ProjectRoot 'logs'
$PidDir = Join-Path $ProjectRoot '.pids'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
if (-not (Test-Path $PidDir)) { New-Item -ItemType Directory -Path $PidDir | Out-Null }

# Load .env variables into environment
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
        $parts = $line.Split('=', 2)
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($key, $val, [System.EnvironmentVariableTarget]::Process)
    }
}

$Port = if ($env:POSTGRES_PORT) { [int]$env:POSTGRES_PORT } else { 5433 }
$DbPath = Join-Path $ProjectRoot '.postgres_runtime'
$PgBin = 'C:\Program Files\PostgreSQL\18\bin'

# 2. Database Startup (.postgres_runtime)
Write-Host ''
Write-Host "[1/5] Checking PostgreSQL (Port $Port)..." -ForegroundColor Yellow

# Clean up stale postmaster.pid if server died unexpectedly
if (Test-Path "$DbPath\postmaster.pid") {
    $firstLine = (Get-Content "$DbPath\postmaster.pid" -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($firstLine) {
        $oldPid = [int]$firstLine.Trim()
        $existingProc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if (-not $existingProc) {
            Remove-Item "$DbPath\postmaster.pid" -Force -ErrorAction SilentlyContinue
        }
    }
}

$pgIsReady = Join-Path $PgBin 'pg_isready.exe'
$dbReady = $false
if (Test-Path $pgIsReady) {
    & $pgIsReady -h 127.0.0.1 -p $Port 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $dbReady = $true }
} else {
    $dbReady = Test-PortOnline '127.0.0.1' $Port
}

if ($dbReady) {
    Write-Host "  -> PostgreSQL is already running and ready on port $Port." -ForegroundColor Green
} else {
    Write-Host "  -> Starting PostgreSQL from $DbPath on port $Port..." -ForegroundColor Cyan
    $pgExe = Join-Path $PgBin 'postgres.exe'
    if (-not (Test-Path $pgExe)) {
        Write-Host "  [ERROR] PostgreSQL binary not found at $pgExe" -ForegroundColor Red
        exit 1
    }

    $pgLog = Join-Path $LogDir 'postgres.log'
    $pgErr = Join-Path $LogDir 'postgres.err.log'
    $dbProc = Start-Process -FilePath $pgExe -ArgumentList '-D', $DbPath, '-p', $Port.ToString() -RedirectStandardOutput $pgLog -RedirectStandardError $pgErr -PassThru
    Set-Content -Path (Join-Path $PidDir 'db.pid') -Value $dbProc.Id

    # Wait for DB ready to accept queries
    $ready = $false
    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path $pgIsReady) {
            & $pgIsReady -h 127.0.0.1 -p $Port 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $ready = $true
                break
            }
        } elseif (Test-PortOnline '127.0.0.1' $Port) {
            Start-Sleep -Seconds 2
            $ready = $true
            break
        }
    }
    if ($ready) {
        Write-Host "  -> PostgreSQL started and accepting connections (PID: $($dbProc.Id))." -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Timed out waiting for PostgreSQL to become ready on port $Port." -ForegroundColor Red
        exit 1
    }
}

# 3. Database Migrations
Write-Host ''
Write-Host '[2/5] Checking Alembic Database Migrations...' -ForegroundColor Yellow
$dbUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'metroscope_user' }
$dbPass = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { 'metroscope_secure_password' }
$dbName = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'metroscope' }
$env:PYTHONPATH = 'backend'
$env:DATABASE_URL = "postgresql+asyncpg://${dbUser}:${dbPass}@127.0.0.1:${Port}/${dbName}"
$env:DATABASE_SYNC_URL = "postgresql://${dbUser}:${dbPass}@127.0.0.1:${Port}/${dbName}"

Push-Location (Join-Path $ProjectRoot 'backend')
$migExitCode = 1
$migOutput = @()
for ($attempt = 1; $attempt -le 3; $attempt++) {
    $prevErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $migOutput = & python -m alembic upgrade head 2>&1
    $migExitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevErrorAction
    if ($migExitCode -eq 0) { break }
    Start-Sleep -Seconds 2
}
Pop-Location

if ($migExitCode -ne 0) {
    Write-Host '  [ERROR] Alembic database migration failed:' -ForegroundColor Red
    $migOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    exit 1
}
Write-Host '  -> Database migrations are up to date (HEAD: 0012_article_full_text_rights).' -ForegroundColor Green

# 4. Start Backend API
Write-Host ''
Write-Host '[3/5] Starting FastAPI Backend API (Port 8000)...' -ForegroundColor Yellow
$backendLog = Join-Path $LogDir 'backend.log'
$backendErr = Join-Path $LogDir 'backend.err.log'
$backendProc = Start-Process -FilePath 'python' -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory (Join-Path $ProjectRoot 'backend') -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr -PassThru
Set-Content -Path (Join-Path $PidDir 'backend.pid') -Value $backendProc.Id

# Wait for backend health
$backendOk = $false
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -eq 200) {
            $backendOk = $true
            break
        }
    } catch {}
}
if ($backendOk) {
    Write-Host "  -> FastAPI Backend running (PID: $($backendProc.Id)) -> http://127.0.0.1:8000" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Backend failed to report healthy status. Check $backendLog and $backendErr" -ForegroundColor Red
    exit 1
}

# 5. Start Background Worker
Write-Host ''
Write-Host '[4/5] Starting APScheduler Background News Worker...' -ForegroundColor Yellow
$workerLog = Join-Path $LogDir 'worker.log'
$workerErr = Join-Path $LogDir 'worker.err.log'
$workerProc = Start-Process -FilePath 'python' -ArgumentList '-m', 'app.workers.main' -WorkingDirectory (Join-Path $ProjectRoot 'backend') -RedirectStandardOutput $workerLog -RedirectStandardError $workerErr -PassThru
Set-Content -Path (Join-Path $PidDir 'worker.pid') -Value $workerProc.Id
Start-Sleep -Seconds 2
Write-Host "  -> APScheduler Worker running (PID: $($workerProc.Id)) [Webz.io, Social, Email dry-run]" -ForegroundColor Green

# 6. Start Next.js Frontend
Write-Host ''
Write-Host '[5/5] Starting Next.js Frontend (Port 3000)...' -ForegroundColor Yellow
$frontendLog = Join-Path $LogDir 'frontend.log'
$frontendErr = Join-Path $LogDir 'frontend.err.log'
$standaloneJs = Join-Path $ProjectRoot 'frontend\.next\standalone\server.js'
$standaloneDir = Join-Path $ProjectRoot 'frontend\.next\standalone'

$env:PORT = '3000'
$env:INTERNAL_API_URL = 'http://127.0.0.1:8000/api/v1'
$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8000/api/v1'
$env:NEXT_PUBLIC_SITE_URL = 'http://localhost:3000'

if (Test-Path $standaloneJs) {
    # Ensure standalone static assets exist so CSS and public assets are served with HTTP 200
    $standaloneStatic = Join-Path $standaloneDir '.next\static'
    $buildStatic = Join-Path $ProjectRoot 'frontend\.next\static'
    if ((-not (Test-Path $standaloneStatic)) -and (Test-Path $buildStatic)) {
        Copy-Item -Path $buildStatic -Destination $standaloneStatic -Recurse -Force
    }
    $standalonePublic = Join-Path $standaloneDir 'public'
    $buildPublic = Join-Path $ProjectRoot 'frontend\public'
    if ((-not (Test-Path $standalonePublic)) -and (Test-Path $buildPublic)) {
        Copy-Item -Path $buildPublic -Destination $standalonePublic -Recurse -Force
    }

    $frontendProc = Start-Process -FilePath 'node' -ArgumentList 'server.js' -WorkingDirectory $standaloneDir -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErr -PassThru
} else {
    $frontendProc = Start-Process -FilePath 'npm' -ArgumentList 'run', 'dev' -WorkingDirectory (Join-Path $ProjectRoot 'frontend') -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErr -PassThru
}
Set-Content -Path (Join-Path $PidDir 'frontend.pid') -Value $frontendProc.Id

# Wait for frontend ready
$feOk = $false
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-WebRequest -Uri 'http://127.0.0.1:3000/' -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -eq 200) {
            $feOk = $true
            break
        }
    } catch {}
}
if ($feOk) {
    Write-Host "  -> Next.js Frontend running (PID: $($frontendProc.Id)) -> http://localhost:3000" -ForegroundColor Green
} else {
    Write-Host "  [NOTICE] Frontend starting up. Check $frontendLog" -ForegroundColor Yellow
}

# 7. Summary Display
$isProd = ($env:ENVIRONMENT -eq 'production') -or ($env:DEBUG -eq 'false')
$docsNotice = if ($isProd) { 'http://127.0.0.1:8000/docs (Disabled in production mode)' } else { 'http://127.0.0.1:8000/docs' }

Write-Host ''
Write-Host '==================================================================' -ForegroundColor Cyan
Write-Host '          METROSCOPE IS NOW LIVE FOR LOCAL MANUAL TESTING        ' -ForegroundColor Green
Write-Host '==================================================================' -ForegroundColor Cyan
Write-Host '  * Frontend UI (Browser Entry) : http://localhost:3000' -ForegroundColor White
Write-Host "  * Backend Interactive Docs    : $docsNotice" -ForegroundColor White
Write-Host '  * Backend Health Probe        : http://127.0.0.1:8000/health' -ForegroundColor White
Write-Host "  * PostgreSQL Database         : 127.0.0.1:$Port (metroscope)" -ForegroundColor White
Write-Host '  * Dry-Run Modes               : SOCIAL_DRY_RUN=true, EMAIL_DRY_RUN=true' -ForegroundColor Cyan
Write-Host '------------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '  * Check Service Status        : .\scripts\local_status.ps1' -ForegroundColor Yellow
Write-Host '  * Inspect Live Logs           : .\scripts\local_logs.ps1' -ForegroundColor Yellow
Write-Host '  * Stop All Services           : .\scripts\local_stop.ps1' -ForegroundColor Yellow
Write-Host '==================================================================' -ForegroundColor Cyan
Write-Host ''

if ($KeepAlive) {
    Write-Host 'Services running in keep-alive monitoring mode.' -ForegroundColor Cyan
    Write-Host 'Press Ctrl+C or run .\scripts\local_stop.ps1 in another window to terminate.' -ForegroundColor Yellow
    while ($true) {
        Start-Sleep -Seconds 10
    }
}

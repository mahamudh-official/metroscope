# ==============================================================================
# MetroScope — Local Stop Script (PowerShell)
# Safely terminates local services WITHOUT deleting database records
# ==============================================================================
$ErrorActionPreference = 'SilentlyContinue'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PidDir = Join-Path $ProjectRoot '.pids'

function Test-PortOnline([string]$hostName, [int]$port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($hostName, $port, $null, $null)
        $wait = $iar.AsyncWaitHandle.WaitOne(500)
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
Write-Host '               STOPPING METROSCOPE LOCAL SERVICES                ' -ForegroundColor Cyan
Write-Host '==================================================================' -ForegroundColor Cyan

function Stop-PidFile($name) {
    $pidFile = Join-Path $PidDir "$name.pid"
    if (Test-Path $pidFile) {
        $pId = Get-Content $pidFile
        if ($pId) {
            $proc = Get-Process -Id ([int]$pId) -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Stopping $name (PID: $pId)..." -ForegroundColor Yellow
                Stop-Process -Id ([int]$pId) -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

Stop-PidFile 'frontend'
Stop-PidFile 'worker'
Stop-PidFile 'backend'
Stop-PidFile 'db'

# Stop PostgreSQL cleanly via pg_ctl if installed
$PgBin = 'C:\Program Files\PostgreSQL\18\bin'
$pgCtl = Join-Path $PgBin 'pg_ctl.exe'
$DbPath = Join-Path $ProjectRoot '.postgres_runtime'
if (Test-Path $pgCtl) {
    if (Test-Path "$DbPath\postmaster.pid") {
        $firstLine = (Get-Content "$DbPath\postmaster.pid" -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($firstLine) {
            $oldPid = [int]$firstLine.Trim()
            $existingProc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
            if ($existingProc) {
                Write-Host 'Stopping PostgreSQL via pg_ctl...' -ForegroundColor Yellow
                & $pgCtl -D $DbPath stop -m fast -s | Out-Null
            } else {
                Remove-Item "$DbPath\postmaster.pid" -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# Stop Docker Compose services only if explicitly running
# Skip by default to prevent hanging if Docker daemon pipe is unresponsive

Start-Sleep -Seconds 1

Write-Host ''
Write-Host 'Verifying port releases...' -ForegroundColor DarkGray
foreach ($port in @(3000, 8000, 5433)) {
    if (-not (Test-PortOnline '127.0.0.1' $port)) {
        Write-Host "  * Port $port : Released" -ForegroundColor Green
    } else {
        try {
            $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($conn -and $conn.OwningProcess) {
                $p = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
                if ($p -and ($p.ProcessName -match "python|node|postgres")) {
                    Write-Host "  * Port $port : Releasing leftover process $($p.ProcessName) (PID: $($p.Id))..." -ForegroundColor Yellow
                    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Milliseconds 500
                }
            }
        } catch {}
        if (-not (Test-PortOnline '127.0.0.1' $port)) {
            Write-Host "  * Port $port : Released" -ForegroundColor Green
        } else {
            Write-Host "  * Port $port : Still occupied by an external process" -ForegroundColor Yellow
        }
    }
}

Write-Host ''
Write-Host 'All MetroScope services stopped safely.' -ForegroundColor Green
Write-Host 'Database records in .postgres_runtime are preserved intact.' -ForegroundColor Cyan
Write-Host ''

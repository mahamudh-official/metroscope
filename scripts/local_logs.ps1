# ==============================================================================
# MetroScope — Local Log Inspection Script (PowerShell)
# Displays or tails logs for backend, worker, frontend, or database
# Usage: .\scripts\local_logs.ps1 [-Service backend|worker|frontend|postgres|all] [-Lines 50] [-Follow]
# ==============================================================================
[CmdletBinding()]
param(
    [ValidateSet("backend", "worker", "frontend", "postgres", "all")]
    [string]$Service = "all",
    [int]$Lines = 30,
    [switch]$Follow
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$LogDir = Join-Path $ProjectRoot "logs"

if (-not (Test-Path $LogDir)) {
    Write-Host "No logs found in $LogDir. Start the application first." -ForegroundColor Yellow
    exit 0
}

function Show-LogFile($filePath, $title) {
    if (Test-Path $filePath) {
        Write-Host "`n=== [LOG: $title] ($filePath) ===" -ForegroundColor Cyan
        if ($Follow) {
            Get-Content -Path $filePath -Tail $Lines -Wait
        } else {
            Get-Content -Path $filePath -Tail $Lines
        }
    } else {
        Write-Host "Log file not yet created: $filePath" -ForegroundColor DarkGray
    }
}

if ($Service -eq "backend" -or $Service -eq "all") {
    Show-LogFile (Join-Path $LogDir "backend.log") "FastAPI Backend"
}
if ($Service -eq "worker" -or $Service -eq "all") {
    Show-LogFile (Join-Path $LogDir "worker.log") "APScheduler Worker"
}
if ($Service -eq "frontend" -or $Service -eq "all") {
    Show-LogFile (Join-Path $LogDir "frontend.log") "Next.js Frontend"
}
if ($Service -eq "postgres" -or $Service -eq "all") {
    Show-LogFile (Join-Path $LogDir "postgres.log") "PostgreSQL Database"
}

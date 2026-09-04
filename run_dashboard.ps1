# Resilient launcher for the EpyScenario dashboard (Windows PowerShell).
#
# - Forces single-threaded native math (numpy/BLAS/numexpr) to avoid a class of
#   intermittent native segfaults when heavy math runs inside Streamlit's worker
#   threads.
# - Opens your browser to the app automatically.
# - Supervises the Streamlit process and restarts it if it exits.
#
# Usage:  .\run_dashboard.ps1 [-Port 8501]
#   If PowerShell blocks the script, run:
#   powershell -ExecutionPolicy Bypass -File .\run_dashboard.ps1

param([int]$Port = 8501)

Set-Location -Path $PSScriptRoot

$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"
$env:NUMEXPR_MAX_THREADS = "1"
$env:VECLIB_MAXIMUM_THREADS = "1"

$py = ".\venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$url = "http://localhost:$Port"
Write-Host ""
Write-Host "  Starting EpyScenario ..." -ForegroundColor Cyan
Write-Host "  Open in your browser:  $url" -ForegroundColor Yellow
Write-Host "  (Leave this window open. Press Ctrl+C here to stop.)" -ForegroundColor DarkGray
Write-Host ""

# Open the browser once, after the server has had a moment to start.
Start-Job -ScriptBlock {
    param($u, $p)
    for ($i = 0; $i -lt 90; $i++) {
        try {
            $r = Invoke-WebRequest "$u/_stcore/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { Start-Process $u; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
} -ArgumentList $url, $Port | Out-Null

while ($true) {
    & $py -m streamlit run Dashboard.py --server.port $Port --server.headless true
    Write-Warning "[supervisor] streamlit exited (code $LASTEXITCODE) - restarting in 2s..."
    Start-Sleep -Seconds 2
}

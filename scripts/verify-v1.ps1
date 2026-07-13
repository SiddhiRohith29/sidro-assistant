param(
    [string]$BackendUrl = "http://127.0.0.1:8021"
)

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Backend virtual environment was not found. Run backend setup first."
    exit 1
}

$env:SIDRO_BACKEND_URL = $BackendUrl
& $Python (Join-Path $Root "scripts\verify_v1.py")
exit $LASTEXITCODE
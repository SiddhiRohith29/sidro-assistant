$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "backend")
$env:SIDRO_DATA_DIR = Join-Path $Root "data"
$env:HF_HOME = Join-Path $Root "local-data\huggingface"
$env:HUGGINGFACE_HUB_CACHE = Join-Path $Root "local-data\huggingface\hub"
$env:HF_HUB_DISABLE_SYMLINKS = "1"
New-Item -ItemType Directory -Force -Path $env:SIDRO_DATA_DIR, $env:HF_HOME, $env:HUGGINGFACE_HUB_CACHE | Out-Null
& ".\.venv\Scripts\Activate.ps1"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8021

$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "frontend")
$env:VITE_API_BASE_URL = "http://127.0.0.1:8021"
$env:npm_config_cache = Join-Path $Root "frontend\.npm-cache"
node ".\node_modules\vite\bin\vite.js" --host 127.0.0.1 --port 5180 --strictPort


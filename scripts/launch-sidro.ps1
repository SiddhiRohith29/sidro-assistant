$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendScript = Join-Path $Root "scripts\run-backend.ps1"
$FrontendScript = Join-Path $Root "scripts\run-frontend.ps1"
$OllamaScript = Join-Path $Root "scripts\start-ollama.ps1"

if (Test-Path -LiteralPath $OllamaScript) {
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $OllamaScript -WorkingDirectory $Root -WindowStyle Hidden
}
Start-Sleep -Seconds 2
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $BackendScript -WorkingDirectory $Root -WindowStyle Hidden
Start-Sleep -Seconds 4
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $FrontendScript -WorkingDirectory $Root -WindowStyle Hidden
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5180"
Write-Host "Sidro launch started. Open http://127.0.0.1:5180 if the browser did not open automatically."

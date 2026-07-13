$Root = Split-Path -Parent $PSScriptRoot
$Ollama = Join-Path $Root "local-bin\ollama\ollama.exe"
$OllamaHome = Join-Path $Root "local-data\ollama-home"
$DesktopModels = "C:\Users\siddh\Desktop\SidRo assistant\sidro\local-data\ollama-models"
$Models = if (Test-Path -LiteralPath $DesktopModels) { $DesktopModels } else { Join-Path $Root "local-data\ollama-models" }

if (-not (Test-Path -LiteralPath $Ollama)) {
    Write-Error "Portable Ollama was not found at $Ollama"
    exit 1
}

New-Item -ItemType Directory -Force -Path $OllamaHome, $Models, (Join-Path $OllamaHome ".ollama") | Out-Null

$env:USERPROFILE = $OllamaHome
$env:HOME = $OllamaHome
$env:OLLAMA_MODELS = $Models
$env:OLLAMA_HOST = "127.0.0.1:11434"

& $Ollama serve

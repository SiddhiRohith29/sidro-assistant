param(
    [string]$Label = "manual"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DataDir = Join-Path $Root "data"
$DbPath = Join-Path $DataDir "sidro.sqlite"
$BackupDir = Join-Path $DataDir "backups"
if (-not (Test-Path -LiteralPath $DbPath)) {
    Write-Error "Sidro database was not found. Start Sidro once before creating a backup."
    exit 1
}
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$SafeLabel = ($Label.ToLower() -replace '[^a-z0-9_-]+', '-') -replace '^-+|-+$', ''
if ([string]::IsNullOrWhiteSpace($SafeLabel)) { $SafeLabel = "manual" }
if ($SafeLabel.Length -gt 40) { $SafeLabel = $SafeLabel.Substring(0, 40) }
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupPath = Join-Path $BackupDir "sidro-backup-$Stamp-$SafeLabel.sqlite"
Copy-Item -LiteralPath $DbPath -Destination $BackupPath -Force
$Manifest = [ordered]@{
    filename = Split-Path -Leaf $BackupPath
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    size_bytes = (Get-Item -LiteralPath $BackupPath).Length
    label = $SafeLabel
}
$Manifest | ConvertTo-Json -Depth 4 | Set-Content -Path ([System.IO.Path]::ChangeExtension($BackupPath, ".json")) -Encoding UTF8
Write-Host "Sidro backup created: $($Manifest.filename)"
Write-Host "Path: $BackupPath"

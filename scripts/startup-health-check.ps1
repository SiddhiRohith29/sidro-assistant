param(
    [string]$BackendUrl = "http://127.0.0.1:8023"
)

$ErrorActionPreference = "Stop"
$Url = $BackendUrl.TrimEnd('/') + "/api/reliability/startup-check"
try {
    $report = Invoke-RestMethod -Uri $Url -TimeoutSec 20
} catch {
    Write-Error "Sidro startup health check failed to reach backend: $($_.Exception.Message)"
    exit 1
}

Write-Host "Sidro reliability phase: $($report.phase)"
foreach ($check in $report.checks) {
    Write-Host "[$($check.status.ToString().ToUpper())] $($check.name): $($check.detail)"
}
foreach ($recommendation in $report.recommendations) {
    Write-Host "- $recommendation"
}
if (-not $report.ok) { exit 1 }
exit 0


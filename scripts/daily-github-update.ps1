param(
    [string]$Message = "Update Sidro daily progress"
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$status = git status --short
if (-not $status) {
    Write-Host "No local changes to commit. GitHub is already up to date."
    exit 0
}

Write-Host "Changes detected:"
Write-Host $status

git add .
git commit -m $Message
if ($LASTEXITCODE -ne 0) {
    Write-Error "Commit failed. Check the message above."
    exit $LASTEXITCODE
}

git push
if ($LASTEXITCODE -ne 0) {
    Write-Error "Push failed. Check your GitHub login/network and try again."
    exit $LASTEXITCODE
}

Write-Host "Sidro changes pushed to GitHub."
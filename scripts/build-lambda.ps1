$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Push-Location $projectDir
try {
    uv run --no-sync python scripts/build_lambda.py
    if ($LASTEXITCODE -ne 0) { throw 'Lambda artifact build failed' }
} finally {
    Pop-Location
}

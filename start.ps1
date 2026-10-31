param([ValidateRange(1024,65535)][int]$Port = 8002)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
}
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
& '.venv/Scripts/python.exe' backend/prepare_env.py
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare environment configuration.' }
& '.venv/Scripts/python.exe' -m pip install -r backend/requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
Push-Location frontend-react
try {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host "Open http://127.0.0.1:$Port after startup. Press Ctrl+C to stop."
& '.venv/Scripts/python.exe' -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port $Port

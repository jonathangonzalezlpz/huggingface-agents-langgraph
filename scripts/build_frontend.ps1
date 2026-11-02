# Builds the Studio frontend into src/huggingface_agents_langgraph/static/app.
# The same steps work on any OS with Node: `cd frontend; npm ci; npm run build`.
$ErrorActionPreference = 'Stop'

$frontend = Join-Path (Split-Path -Parent $PSScriptRoot) 'frontend'
Push-Location $frontend
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed. Check that your Node version meets package.json "engines".' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'npm run build failed.' }
    Write-Host 'Built. Start the server and open http://127.0.0.1:7860/app/'
}
finally {
    Pop-Location
}

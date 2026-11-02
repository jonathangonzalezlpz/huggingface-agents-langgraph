[CmdletBinding()]
param(
    [ValidateSet("frontend", "terminal")]
    [string]$Mode,
    [string]$Model = "Qwen/Qwen3-8B-GGUF:Q5_K_M",
    [ValidateSet("single", "exclusive")]
    [string]$ModelMode = "single",
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8080,
    [ValidateRange(60, 86400)]
    [int]$SleepIdleSeconds = 300,
    [ValidateRange(30, 1800)]
    [int]$StartupTimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$llmScript = Join-Path $PSScriptRoot "start_local_llm.ps1"
if ($ModelMode -eq "exclusive") {
    $llmScript = Join-Path $PSScriptRoot "start_model_router.ps1"
}
$env:MODEL_SERVER_MODE = $ModelMode
$env:LLM_DEFAULT_MODEL = $Model
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue

if ($null -eq $uvCommand) {
    throw "uv was not found. Install uv before starting the agent."
}

if (-not $Mode) {
    Write-Host "Select how to start the GAIA agent:"
    Write-Host "  1. Frontend (browser)"
    Write-Host "  2. Terminal"
    $selection = Read-Host "Enter 1 or 2"
    $Mode = switch ($selection) {
        "1" { "frontend" }
        "2" { "terminal" }
        default { throw "Choose 1 for frontend or 2 for terminal." }
    }
}

$healthHost = if ($HostAddress -in @("0.0.0.0", "::")) {
    "127.0.0.1"
} else {
    $HostAddress
}
$healthUrl = "http://${healthHost}:${Port}/health"
$llmProcess = $null

try {
    $null = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    Write-Host "LLM server already responds at $healthUrl"
} catch {
    $existingListener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($existingListener) {
        throw "Port $Port is occupied, but no healthy llama.cpp server answered at $healthUrl."
    }

    Write-Host "Starting Qwen via llama.cpp; first startup may download the model..."
    $standardOutput = Join-Path $env:TEMP "huggingface-agents-langgraph-llm.stdout.log"
    $standardError = Join-Path $env:TEMP "huggingface-agents-langgraph-llm.stderr.log"
    $currentPowerShell = (Get-Process -Id $PID).Path
    $llmArguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "`"$llmScript`"",
        "-HostAddress",
        "`"$HostAddress`"",
        "-Port",
        "$Port",
        "-SleepIdleSeconds",
        "$SleepIdleSeconds"
    )
    if ($ModelMode -eq "single") {
        $llmArguments += @("-Model", "`"$Model`"")
    }
    $llmProcess = Start-Process `
        -FilePath $currentPowerShell `
        -ArgumentList $llmArguments `
        -WorkingDirectory $repositoryRoot `
        -RedirectStandardOutput $standardOutput `
        -RedirectStandardError $standardError `
        -WindowStyle Hidden `
        -PassThru

    $ready = $false
    for ($elapsed = 0; $elapsed -lt $StartupTimeoutSeconds; $elapsed += 2) {
        Start-Sleep -Seconds 2
        if ($llmProcess.HasExited) {
            break
        }
        try {
            $null = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
            $ready = $true
            break
        } catch {
            continue
        }
    }

    if (-not $ready) {
        $logTail = @()
        if (Test-Path -LiteralPath $standardOutput) {
            $logTail += Get-Content -LiteralPath $standardOutput -Tail 20
        }
        if (Test-Path -LiteralPath $standardError) {
            $logTail += Get-Content -LiteralPath $standardError -Tail 20
        }
        if ($logTail.Count -gt 0) {
            $logTail | ForEach-Object { Write-Host $_ }
        }
        throw "Qwen did not become ready within $StartupTimeoutSeconds seconds."
    }
    Write-Host "Qwen is ready at $healthUrl"
}

$inventory = Invoke-RestMethod -Uri "http://${healthHost}:${Port}/models" -TimeoutSec 5
$isRouter = @($inventory.data | Where-Object { $null -ne $_.status }).Count -gt 0
if ($ModelMode -eq "exclusive" -and -not $isRouter -and @($inventory.data).Count -gt 0) {
    throw "The existing server is in single-model mode. Stop it before requesting exclusive mode."
}
if ($ModelMode -eq "single" -and $isRouter) {
    throw "The existing server is an exclusive router. Restart with -ModelMode exclusive or stop that server."
}

$env:LLM_BASE_URL = "http://${healthHost}:${Port}/v1"
$uvArguments = @("run", "--extra", "multimedia")
if (Test-Path -LiteralPath (Join-Path $repositoryRoot ".env")) {
    $uvArguments += @("--env-file", ".env")
} else {
    Write-Warning "No .env found. HF_TOKEN may be needed to retrieve GAIA attachments."
}
$uvArguments += @("python", "-m")

if ($Mode -eq "frontend") {
    $uvArguments += "huggingface_agents_langgraph.web_app"
    $studioIndex = Join-Path $repositoryRoot "src/huggingface_agents_langgraph/static/app/index.html"
    if (-not (Test-Path $studioIndex)) {
        Write-Warning "The Studio interface is not built yet, so the page will only explain how to build it. Run scripts/build_frontend.ps1 (needs Node; see docs/frontend-seguridad.md) and reload."
    }
    Write-Host "Starting frontend at http://127.0.0.1:7860 (opens the Studio at /app/)"
} else {
    $uvArguments += "huggingface_agents_langgraph.cli"
    Write-Host "Starting terminal runner."
}

Push-Location $repositoryRoot
try {
    & $uvCommand.Source @uvArguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

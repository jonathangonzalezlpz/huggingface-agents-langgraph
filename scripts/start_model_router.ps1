[CmdletBinding()]
param(
    [ValidateSet("127.0.0.1")]
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8080,
    [ValidateRange(4096, 32768)]
    [int]$ContextSize = 16384,
    [ValidateRange(60, 86400)]
    [int]$SleepIdleSeconds = 300,
    [ValidateRange(-1, 2147483647)]
    [Nullable[int]]$CacheRamMiB = $null
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$uvCommand = Get-Command uv -ErrorAction Stop
$env:MODEL_SERVER_MODE = "exclusive"
$serverArguments = @("run")
if (Test-Path -LiteralPath (Join-Path $repositoryRoot ".env")) {
    $serverArguments += @("--env-file", ".env")
}
$serverArguments += @(
    "python", "-m", "huggingface_agents_langgraph.model_server", "serve",
    "--port", "$Port", "--context", "$ContextSize",
    "--sleep-idle-seconds", "$SleepIdleSeconds"
)
if ($null -ne $CacheRamMiB) {
    $serverArguments += @("--cache-ram", "$CacheRamMiB")
}
Push-Location $repositoryRoot
try {
    & $uvCommand.Source @serverArguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

[CmdletBinding()]
param(
    [string]$Model = "Qwen/Qwen3-8B-GGUF:Q5_K_M",
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8080,
    [ValidateRange(60, 86400)]
    [int]$SleepIdleSeconds = 300
)

$ErrorActionPreference = "Stop"

$llamaCommand = Get-Command llama -ErrorAction SilentlyContinue
if ($null -eq $llamaCommand) {
    throw "llama.cpp was not found. Install it with: winget install llama.cpp"
}

$serverArguments = @(
    "serve"
    "-hf"
    $Model
    "--host"
    $HostAddress
    "--port"
    $Port.ToString()
    "--sleep-idle-seconds"
    $SleepIdleSeconds.ToString()
    "--no-webui"
)

& $llamaCommand.Path @serverArguments
exit $LASTEXITCODE

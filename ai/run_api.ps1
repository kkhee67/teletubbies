param(
    [int]$Port = 8000,
    [switch]$NoReload
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$sourcePath = Join-Path $projectRoot "src"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "프로젝트 가상환경을 찾을 수 없습니다: $pythonPath"
}

$uvicornArgs = @(
    "-m", "uvicorn",
    "api:app",
    "--app-dir", $sourcePath,
    "--host", "127.0.0.1",
    "--port", $Port
)

if (-not $NoReload) {
    $uvicornArgs += "--reload"
}

& $pythonPath $uvicornArgs

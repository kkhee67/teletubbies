param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "가상환경을 찾을 수 없습니다: $Python"
}

& $Python (Join-Path $ProjectRoot "src\preprocess_consultations.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python (Join-Path $ProjectRoot "src\structure_cases.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python (Join-Path $ProjectRoot "src\build_product_context.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

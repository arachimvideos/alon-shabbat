$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $venvPython)) {
  $python = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Test-Path $bundledPython) { $bundledPython } else { throw "Python לא נמצא" }
  & $python -m venv (Join-Path $backend ".venv")
  & $venvPython -m pip install -r (Join-Path $backend "requirements.txt")
}

Set-Location $backend
& $venvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000


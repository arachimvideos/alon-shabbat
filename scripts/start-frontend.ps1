$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$bundledNodeBin = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$bundledPnpm = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd"

if (Test-Path $bundledNodeBin) {
  $env:PATH = "$bundledNodeBin;$env:PATH"
}

$pnpm = if (Get-Command pnpm -ErrorAction SilentlyContinue) { "pnpm" } elseif (Test-Path $bundledPnpm) { $bundledPnpm } else { throw "pnpm לא נמצא" }

Set-Location $frontend
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
  & $pnpm install
}
& $pnpm build
& (Join-Path $bundledNodeBin "node.exe") "serve-dist.mjs"

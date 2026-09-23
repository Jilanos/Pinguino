# Full Windows validation: install, checks, synthetic browser journey and opt-in real MT5 journey.
# Usage (PowerShell, from the repository root):
#   .\scripts\windows-validation.ps1 -Mt5Start 2026-07-25T00:00 -Mt5End 2026-09-19T00:00
# Logs land in reports\windows-validation\<timestamp>\ (ignored by Git).
param(
    [string]$Mt5Start = "",
    [string]$Mt5End = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$out = Join-Path $root "reports\windows-validation\$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$summary = Join-Path $out "summary.txt"

function Step([string]$name, [string]$dir, [scriptblock]$block) {
    Push-Location (Join-Path $root $dir)
    $log = Join-Path $out "$name.log"
    $watch = [Diagnostics.Stopwatch]::StartNew()
    # Native tools write progress to stderr; only their exit code decides success.
    $ErrorActionPreference = "Continue"
    try {
        & $block *>&1 | ForEach-Object { "$_" } | Out-File -FilePath $log -Encoding utf8
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = "Stop"
        Pop-Location
    }
    $watch.Stop()
    $line = "{0,-22} exit={1} seconds={2:N1}" -f $name, $code, $watch.Elapsed.TotalSeconds
    Add-Content $summary $line
    Write-Host $line
    if ($code -ne 0) { throw "step $name failed, see $log" }
}

$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Add-Content $summary ("host: {0} {1}; CPU: {2} ({3} logical); RAM: {4:N1} GiB" -f `
    $os.Caption, $os.Version, $cpu.Name.Trim(), $cpu.NumberOfLogicalProcessors, ($os.TotalVisibleMemorySize / 1MB))
Add-Content $summary ("uv: {0}; node: {1}; git: {2}" -f (uv --version), (node --version), (git --version))

Step "backend-sync" "backend" { uv sync --all-extras }
Step "backend-lint" "backend" { uv run ruff check . }
Step "backend-types" "backend" { uv run mypy }
$env:PINGUINO_MT5_LIVE = "1"
Step "backend-tests" "backend" { uv run pytest -q -rs }
Remove-Item Env:\PINGUINO_MT5_LIVE
Step "frontend-install" "frontend" { npm ci --no-audit --no-fund }
Step "frontend-types" "frontend" { npx tsc --noEmit }
Step "frontend-tests" "frontend" { npx vitest run }
Step "frontend-build" "frontend" { npx vite build }
Step "browser-install" "frontend" { npx playwright install chromium }
if ($Mt5Start -and $Mt5End) {
    $env:PINGUINO_E2E_MT5_START = $Mt5Start
    $env:PINGUINO_E2E_MT5_END = $Mt5End
}
Step "browser-journeys" "frontend" { npx playwright test }
Copy-Item (Join-Path $root "frontend\test-results\e2e-report.json") $out -ErrorAction SilentlyContinue
Write-Host "Evidence written to $out"

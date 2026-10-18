# Runs the repository's local verification gates on Windows.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Python = if ($env:QDT_TEST_PYTHON) { $env:QDT_TEST_PYTHON } elseif (Test-Path $VenvPython) { $VenvPython } else { "python" }

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Directory,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name"
    Push-Location (Join-Path $RepoRoot $Directory)
    try {
        $global:LASTEXITCODE = 0
        & $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Step '$Name' failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "pyproject TOML parse" "." {
    & $Python -c "import pathlib,tomllib; [tomllib.load(open(p,'rb')) for p in pathlib.Path('services').glob('*/pyproject.toml')]; print('pyproject toml ok')"
}

Invoke-Step "Python services (isolated configuration)" "." {
    & $Python -X utf8 -B scripts/check-python.py
}

Invoke-Step "release privacy regression tests" "." {
    & $Python -X utf8 -B -m unittest discover -s scripts/tests -v
}

Invoke-Step "desktop node tests" "apps/desktop" {
    & node --test "tests/*.test.mjs"
}

Invoke-Step "desktop typecheck" "apps/desktop" {
    & npm run check
}

Invoke-Step "tauri cargo test" "apps/desktop/src-tauri" {
    & cargo test --features custom-protocol
}

Invoke-Step "tauri cargo check" "apps/desktop/src-tauri" {
    & cargo check --features custom-protocol
}

Write-Host ""
Write-Host "All verification gates passed."

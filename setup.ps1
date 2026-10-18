param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$Version = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($LASTEXITCODE -ne 0 -or $Version -ne '3.12') { throw 'Use Python 3.12 x64: ./setup.ps1 -Python <path-to-python.exe>' }
function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Setup failed (exit $LASTEXITCODE)." }
}
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Invoke-Checked $Python @('-m','venv',(Join-Path $Root '.venv'))
}
$env:PIP_DISABLE_PIP_VERSION_CHECK='1'
Invoke-Checked $VenvPython @('-m','pip','install','--timeout','30','--retries','3','-r',(Join-Path $Root 'requirements-windows.lock.txt'))
foreach ($Package in @('scholar-translator','translator-core','agent-adapters')) {
    Invoke-Checked $VenvPython @('-m','pip','install','--no-deps','-e',(Join-Path $Root "services\$Package"))
}
Invoke-Checked $VenvPython @('-m','pip','install','pytest==8.4.2')
Invoke-Checked $VenvPython @('-c','import scholar_translator.cli, qdt, qdt_agents, fitz, kiwipiepy; print("Python environment ready.")')
Write-Host 'Next: npm ci in apps/desktop, then npm run tauri dev. Install Tesseract OCR for image text.'

$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "dist\AudioDNAStudioPro\AudioDNAStudioPro.exe"
if (-not (Test-Path $exe)) {
    throw "Missing EXE: $exe"
}
Write-Host "Found EXE: $exe"
& $exe --self-check
Write-Host "Windows release verification completed."

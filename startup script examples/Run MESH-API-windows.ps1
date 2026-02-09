# RUN-MESH-API.ps1
param(
    [string[]]$ScriptArgs
)

# --- Always start in the folder where this script lives ---
Set-Location -Path $PSScriptRoot

# --- Try to activate venv if it exists ---
$venv = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    . $venv
}

# --- Decide which script to run ---
$scriptFile = @("mesh-api.py") | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($null -eq $scriptFile) {
    Write-Host "[ERROR] Could not find mesh-api.py in $PWD" -ForegroundColor Red
    Write-Host "Available Python files:" -ForegroundColor Yellow
    Get-ChildItem -Filter *.py | ForEach-Object { $_.Name }
    exit 1
}

# --- Run the script, passing through any arguments ---
Write-Host "[INFO] Running $scriptFile with args: $ScriptArgs" -ForegroundColor Cyan
python $scriptFile @ScriptArgs

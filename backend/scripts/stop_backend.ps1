$workspaceRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$targets = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match 'python|powershell' -and
        $_.CommandLine -match 'uvicorn app\.main:app|run_backend\.ps1' -and
        $_.CommandLine -match [regex]::Escape($workspaceRoot)
    }

if (-not $targets) {
    Write-Host "No backend process found."
    exit 0
}

$targets | ForEach-Object {
    try {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped backend process:" $_.ProcessId
    } catch {
        Write-Warning "Failed to stop backend process $($_.ProcessId): $($_.Exception.Message)"
    }
}

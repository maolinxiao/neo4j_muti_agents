$workspaceRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$targets = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match 'node|powershell' -and
        $_.CommandLine -match 'vite|run_frontend\.ps1' -and
        $_.CommandLine -match [regex]::Escape($workspaceRoot)
    }

if (-not $targets) {
    Write-Host "No frontend process found."
    exit 0
}

$targets | ForEach-Object {
    try {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped frontend process:" $_.ProcessId
    } catch {
        Write-Warning "Failed to stop frontend process $($_.ProcessId): $($_.Exception.Message)"
    }
}

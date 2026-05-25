$frontendRoot = (Resolve-Path "$PSScriptRoot\..").Path
$nodeHome = "E:\nodejs"

if (Test-Path $nodeHome) {
    $env:Path = "$nodeHome;$env:Path"
}

Set-Location $frontendRoot
npm run dev -- --host 0.0.0.0 --port 5173

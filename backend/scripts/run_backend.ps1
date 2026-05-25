$backendRoot = (Resolve-Path "$PSScriptRoot\..").Path
$vendorRoot = (Resolve-Path "$PSScriptRoot\..\_vendor").Path
$env:PYTHONPATH = "$vendorRoot;$backendRoot"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

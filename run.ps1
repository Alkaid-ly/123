$ErrorActionPreference = "Stop"

$venvDir = ".\\.venv"
$python = Join-Path $venvDir "Scripts\\python.exe"

$needsRecreate = $false
if (Test-Path (Join-Path $venvDir "pyvenv.cfg")) {
  $homeLine = Select-String -Path (Join-Path $venvDir "pyvenv.cfg") -Pattern "^\s*home\s*=" -ErrorAction SilentlyContinue
  if ($homeLine) {
    $venvHome = ($homeLine.Line.Split("=", 2)[1]).Trim()
    if ($venvHome -and (-not (Test-Path (Join-Path $venvHome "python.exe")))) {
      $needsRecreate = $true
    }
  }
}

if ($needsRecreate) {
  Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $python)) {
  python -m venv $venvDir
}

$depsOk = $false
try {
  & $python -c "import fastapi, networkx, pandas, uvicorn" 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    $depsOk = $true
  }
} catch {
  $depsOk = $false
}

if (-not $depsOk) {
  & $python -m pip install -r requirements.txt
}
# 启动后端
& $python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

param(
    [switch]$InstallDependencies,
    [switch]$StartDatabase,
    [string]$WslDistro = 'Ubuntu-24.04'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envFile = Join-Path $projectRoot '.env'
$exampleEnvFile = Join-Path $projectRoot '.env.example'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

function Stop-Setup([string]$Message) {
    Write-Error $Message
    exit 1
}

Push-Location $projectRoot
try {
    Write-Host '[1/4] Python 3.14 확인'
    & py -3.14 --version
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup 'Python 3.14가 없습니다. SETUP.md의 PC 준비 절차를 완료하세요.'
    }

    if (-not (Test-Path -LiteralPath $envFile)) {
        Copy-Item -LiteralPath $exampleEnvFile -Destination $envFile
        Stop-Setup '.env.example을 복사해 .env를 만들었습니다. .env에 로컬 DB 비밀번호를 입력한 뒤 다시 실행하세요.'
    }

    $envLines = Get-Content -LiteralPath $envFile
    $envValues = @{}
    foreach ($line in $envLines) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $envValues[$matches[1]] = $matches[2].Trim('"').Trim("'")
        }
    }
    if (-not $envValues['POSTGRES_PASSWORD'] -or $envValues['POSTGRES_PASSWORD'] -eq 'change-me-locally') {
        Stop-Setup '.env의 POSTGRES_PASSWORD를 팀원이 정한 로컬 비밀번호로 바꾸세요.'
    }
    if (-not $envValues['DATABASE_URL']) {
        Stop-Setup '.env에 DATABASE_URL이 필요합니다.'
    }
    if ($envValues['DATABASE_URL'] -notmatch ':[0-9]+/') {
        Stop-Setup '.env의 DATABASE_URL에 포트 번호가 있는지 확인하세요.'
    }
    $urlPort = [regex]::Match($envValues['DATABASE_URL'], ':(\d+)/').Groups[1].Value
    if ($envValues['POSTGRES_PORT'] -and $envValues['POSTGRES_PORT'] -ne $urlPort) {
        Stop-Setup '.env의 POSTGRES_PORT와 DATABASE_URL 포트가 다릅니다. 같은 값으로 맞추세요.'
    }

    if (-not (Test-Path -LiteralPath $venvPython)) {
        if (-not $InstallDependencies) {
            Stop-Setup '.venv가 없습니다. -InstallDependencies 옵션으로 가상환경과 패키지를 준비하세요.'
        }
        & py -3.14 -m venv .venv
        if ($LASTEXITCODE -ne 0) { Stop-Setup '가상환경 생성에 실패했습니다.' }
    }

    if ($InstallDependencies) {
        Write-Host '[2/4] Python 의존성 설치'
        & $venvPython -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { Stop-Setup 'pip 업그레이드에 실패했습니다.' }
        & $venvPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { Stop-Setup 'requirements.txt 설치에 실패했습니다.' }
    } else {
        Write-Host '[2/4] 설치된 Python 의존성 확인'
    }
    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Python 의존성 검사에 실패했습니다.' }

    Write-Host "[3/4] WSL 배포판 '$WslDistro' 및 Docker Compose 확인"
    $linuxPath = (& wsl.exe -d $WslDistro -- wslpath -a $projectRoot 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $linuxPath) {
        Stop-Setup "WSL 배포판 '$WslDistro'를 찾지 못했습니다. WSL 통합 설정을 확인하거나 -WslDistro로 배포판 이름을 지정하세요."
    }
    $shellPath = "'" + $linuxPath.Replace("'", "'\''") + "'"
    $composeCheck = "cd -- $shellPath && docker compose config --quiet"
    & wsl.exe -d $WslDistro -- bash -lc $composeCheck
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup 'WSL Docker CLI 또는 Docker Compose 설정 확인에 실패했습니다. Docker Desktop의 WSL 통합과 .env를 확인하세요.'
    }

    if ($StartDatabase) {
        Write-Host '[4/4] PostgreSQL 시작 및 상태 확인'
        & wsl.exe -d $WslDistro -- bash -lc "cd -- $shellPath && docker compose up -d && docker compose ps"
        if ($LASTEXITCODE -ne 0) { Stop-Setup 'PostgreSQL 시작에 실패했습니다.' }
    } else {
        Write-Host '[4/4] 설정 검증 완료. DB 시작을 요청하지 않아 현재 컨테이너 상태는 변경하지 않았습니다.'
        & wsl.exe -d $WslDistro -- bash -lc "cd -- $shellPath && docker compose ps"
    }

    Write-Host '설정 확인 완료. 로컬 RAG 검색 명령은 SETUP.md의 앱과 검색 확인 절을 따르세요.'
} finally {
    Pop-Location
}

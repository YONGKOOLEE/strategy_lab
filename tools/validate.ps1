# 후보 전략을 운영 저장소의 검증 실행기(CP-030)로 미리 돌려 본다. 운영 저장소에는 아무것도 쓰지 않는다.
# 결과: 전략실 results\<날짜>-<전략폴더>\ (판정표 validation-v<n>.md, 실행별 trades.csv·equity.csv·summary.json)
# 실행 예 (평일 06:40~16:00 금지 — PAPER 무인 운영과 같은 PC):
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\validate.ps1 -Candidate example_sma -Class ExampleSmaV1 -Version 1
# 이 결과는 연구 참고다. 공식 판정은 운영 저장소에서 다시 돌린다.
param(
    [Parameter(Mandatory = $true)][string]$Candidate,   # candidates 아래 폴더 이름 (밑줄)
    [Parameter(Mandatory = $true)][string]$Class,       # strategy.py 안의 클래스 이름
    [Parameter(Mandatory = $true)][int]$Version,        # params-v<n>.toml 의 n, 판정표 번호
    [string]$EvalTime = '09:30',
    [int]$Workers = 2,
    [string]$Ops = 'C:\AI\trading_system\trading_system',
    [string]$Params = '',   # 대조군·프로필용 파라미터 파일(기본 params-v<n>.toml). 지정하면 -Label도 지정한다
    [string]$Label = '',    # 결과 폴더 접미(results\<날짜>-<후보>-<라벨>) — 같은 날 같은 버전을 다른 조건으로 돌릴 때 충돌 방지
    [string]$Data = '',     # 일봉 폴더(기본 data\daily). 모드 2 목록 시험은 data\lists\<이름>
    [string]$Limits = '',   # 한도 프로필. 운영 승인 연구 프로필: C:\AI\trading_system\trading_system\config\limits.research.toml (A-093). 비우면 운영 기본(legacy, 상한가 L1)
    [string]$UniverseHistory = '',   # [CP-034] U-B 전략 목록 이력 CSV(date,code). 진짜 판정 시점 목록일 때만(없으면 C-7 표시)
    [string]$Allocation = '',        # [CP-034] 배분 규칙 패키지.모듈:클래스 (예 candidates.regime_kospi.strategy:RegimeKospiV1) — 대조 판정
    [string]$AllocationParams = '',  # 배분 규칙 파라미터 파일(절대 경로)
    [string]$Index = '',             # 지수 일봉 CSV (기본: 배분 규칙 지정 시 data\index\001.csv)
    [switch]$UB,       # [CP-034] U-B 전략: --universe-from-data를 넘기지 않는다(운영 등록 검사가 universe 비움을 요구). 스냅샷 = 데이터 폴더 전체
    [switch]$Holiday   # 평일 휴장일(PAPER run 없음)에만 붙인다: 시간 제한을 건너뛴다
)
$ErrorActionPreference = 'Stop'
$lab = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (($Params -ne '' -or $Data -ne '') -and $Label -eq '') { throw '-Params/-Data를 지정하면 -Label도 지정한다(기준 실행과 결과 폴더가 섞이지 않게)' }
$params = if ($Params -ne '') { $Params } else { Join-Path $lab "candidates\$Candidate\params-v$Version.toml" }
$data = if ($Data -ne '') { $Data } else { Join-Path $lab 'data\daily' }
$hol = Join-Path $lab 'data\holidays-2016-2023.json'
$suffix = if ($Label -ne '') { "-$Label" } else { '' }
$out = Join-Path $lab ("results\" + (Get-Date -Format 'yyyyMMdd') + "-$Candidate$suffix")
$py = Join-Path $Ops '.venv\Scripts\python.exe'
foreach ($p in @($params, $data, $hol, $py)) { if (-not (Test-Path $p)) { throw "없음: $p (데이터는 tools\sync-data.ps1 먼저)" } }

$now = Get-Date
if (-not $Holiday -and $now.DayOfWeek -ne 'Saturday' -and $now.DayOfWeek -ne 'Sunday' -and $now.TimeOfDay -ge [TimeSpan]'06:40' -and $now.TimeOfDay -lt [TimeSpan]'16:00') {
    throw '평일 06:40~16:00에는 실행하지 않는다 (PAPER 무인 운영 보호). 평일 휴장일이면 -Holiday 를 붙인다.'
}

$extra = @()
if (-not $UB) { $extra += @('--universe-from-data') }
if ($Limits -ne '') { $extra += @('--limits', $Limits) }
if ($UniverseHistory -ne '') { $extra += @('--universe-history', $UniverseHistory) }
if ($Allocation -ne '') {
    if ($AllocationParams -eq '') { throw '-Allocation 지정 시 -AllocationParams 필요' }
    $idx = if ($Index -ne '') { $Index } else { Join-Path $lab 'data\index\001.csv' }
    $extra += @('--allocation', $Allocation, '--allocation-params', $AllocationParams, '--index', $idx)
}
$env:PYTHONPATH = (Join-Path $Ops 'src') + ';' + $lab
Push-Location $Ops
try {
    & $py (Join-Path $Ops 'scripts\validate-strategy.py') `
        --strategy "candidates.$Candidate.strategy:$Class" --params $params --data $data `
        --report-version $Version --eval-time $EvalTime `
        --universe-note '전략실 미리 돌려 보기(연구 참고, 공식 판정 아님)' `
        --holidays-json $hol --workers $Workers --out-root $out @extra
    $code = $LASTEXITCODE
} finally { Pop-Location }
Write-Output "종료 코드 $code, 결과 폴더 $out"
exit $code

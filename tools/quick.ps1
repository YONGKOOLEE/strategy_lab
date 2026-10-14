# 1차 선별기 — 후보를 창 1~2개만 빨리 돌려 거래당 기대값을 본다 (tools\quick.py). 운영 저장소에는 쓰지 않는다.
# 실행 예 (평일 06:40~16:00 금지 — PAPER 무인 운영과 같은 PC):
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\quick.ps1 -Candidate example_sma -Class ExampleSmaV1 -Version 1
# 기대 결과: 창별 표 + "합산 | 거래 N | 거래당 기대값 …원" + "1차 판단: …" + 결과 폴더. 보통 수 분.
param(
    [Parameter(Mandatory = $true)][string]$Candidate,
    [Parameter(Mandatory = $true)][string]$Class,
    [Parameter(Mandatory = $true)][int]$Version,
    [string]$Windows = '4,7',     # 검증 창 k (1~7 = 2019~2025). 기본 4(2022 하락장)·7(2025)
    [string]$Label = 'base',      # 파라미터를 바꿨으면 라벨도 바꾼다 (결과 폴더·시도 장부에 기록)
    [string]$EvalTime = '09:30',
    [string]$Params = '',         # 대조군·변형 실험용 파라미터 파일(기본은 params-v<n>.toml). 지정하면 -Label도 바꾼다
    [string]$Limits = '',         # 규모 실험용 한도 파일(전략실 사본, 예 research\limits-scale-test.toml). 지정하면 -Label도 바꾼다
    [string]$Data = '',           # 모드 2(사용자 목록) 시험: data\lists\<이름> 폴더(tools\make_list.py로 생성). 지정하면 -Label도 바꾼다
    [string]$Ops = 'C:\AI\trading_system\trading_system',
    [switch]$Holiday
)
$ErrorActionPreference = 'Stop'
$lab = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path $Ops '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "운영 .venv 파이썬 없음: $py" }
$now = Get-Date
if (-not $Holiday -and $now.DayOfWeek -ne 'Saturday' -and $now.DayOfWeek -ne 'Sunday' -and $now.TimeOfDay -ge [TimeSpan]'06:40' -and $now.TimeOfDay -lt [TimeSpan]'16:00') {
    throw '평일 06:40~16:00에는 실행하지 않는다 (PAPER 무인 운영 보호). 평일 휴장일이면 -Holiday 를 붙인다.'
}
$extra = @()
if ($Params -ne '') { $extra += @('--params', $Params) }
if ($Limits -ne '') { $extra += @('--limits', $Limits) }
if ($Data -ne '') { $extra += @('--data', $Data) }
& $py (Join-Path $lab 'tools\quick.py') --candidate $Candidate --cls $Class --version $Version --windows $Windows --label $Label --eval-time $EvalTime --ops $Ops @extra
exit $LASTEXITCODE

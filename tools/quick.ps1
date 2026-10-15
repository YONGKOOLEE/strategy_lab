# 1차 선별기 — 후보를 창 1~2개만 빨리 돌려 거래당 기대값을 본다 (tools\quick.py). 운영 저장소에는 쓰지 않는다.
# 실행 예 (언제든 가능 — 우선순위 BelowNormal로 같은 PC의 PAPER 엔진에 CPU 양보):
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\quick.ps1 -Candidate example_sma -Class ExampleSmaV1 -Version 1
# 기대 결과: 창별 표 + "합산 | 거래 N | 거래당 기대값 …원" + "1차 판단: …" + 결과 폴더. 보통 수 분.
param(
    [Parameter(Mandatory = $true)][string]$Candidate,
    [Parameter(Mandatory = $true)][string]$Class,
    [Parameter(Mandatory = $true)][int]$Version,
    [string]$Windows = '',        # 창 k (1~7). 비우면 4,7(2022 하락장·2025), -Train이면 1(학습 2016~2018)
    [switch]$Train,               # 학습 창 모드: 창 k의 학습 구간 실행(파라미터 선택용, 판정 아님)
    [string]$TrainStart = '',     # 학습 구간 시작일 YYYY-MM-DD(워밍업 공통화, 예 2017-01-01)
    [string]$TrainEnd = '',
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
# 2026-10-14 사용자 결정(운영시간 제약 해제): 시간 금지 대신 낮은 우선순위 — 같은 PC의 PAPER 엔진이 항상 CPU를 먼저 쓴다(자식 python 상속)
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
$extra = @()
if ($Params -ne '') { $extra += @('--params', $Params) }
if ($Limits -ne '') { $extra += @('--limits', $Limits) }
if ($Data -ne '') { $extra += @('--data', $Data) }
if ($Windows -ne '') { $extra += @('--windows', $Windows) }
if ($Train) { $extra += '--train' }
if ($TrainStart -ne '') { $extra += @('--train-start', $TrainStart) }
if ($TrainEnd -ne '') { $extra += @('--train-end', $TrainEnd) }
& $py (Join-Path $lab 'tools\quick.py') --candidate $Candidate --cls $Class --version $Version --label $Label --eval-time $EvalTime --ops $Ops @extra
exit $LASTEXITCODE

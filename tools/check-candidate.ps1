# 후보 구조 검사 — 운영 구조 시험(import 규칙)·적재·파라미터 범위·3파일·strategy.md 빈 칸을 미리 확인한다 (tools\check-candidate.py).
# 가벼운 실행(수 초)이라 시간 제한 없음. 운영 저장소에는 쓰지 않는다.
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\check-candidate.ps1 -Candidate example_sma -Class ExampleSmaV1 -Version 1
# 기대 결과: "적재 OK: …" 뒤 "구조 검사 통과" (종료 코드 0) 또는 "위반 N건" 목록 (종료 코드 1).
param(
    [Parameter(Mandatory = $true)][string]$Candidate,
    [Parameter(Mandatory = $true)][string]$Class,
    [Parameter(Mandatory = $true)][int]$Version,
    [string]$Ops = 'C:\AI\trading_system\trading_system'
)
$ErrorActionPreference = 'Stop'
$lab = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path $Ops '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "운영 .venv 파이썬 없음: $py" }
& $py (Join-Path $lab 'tools\check-candidate.py') --candidate $Candidate --cls $Class --version $Version --ops $Ops
exit $LASTEXITCODE

# 운영 저장소의 키움 일봉 CSV를 전략실 data\daily로 복사한다 (운영 저장소는 읽기만).
# 2026-01-01 이후 행은 잘라 낸다 — 최종 확인 구간(운영 CP-030 D-163)은 연구에 쓰지 않는다.
# 원본 폴더에 index\ 하위 폴더(지수, 예 001.csv = KOSPI)가 있으면 data\index\ 로 같은 규칙으로 복사한다.
# 잘라 낸 뒤 봉이 0개인 종목(2026년 상장 등)은 복사하지 않는다.
# 실행: powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\sync-data.ps1
#   (원본 폴더를 바꾸려면 -Source <경로>. 2026-10-11부터 기본값 = 코스피200 201종목 + KOSPI 지수)
param(
    [string]$Source = 'C:\AI\trading_system\trading_system\var\backtest\data\kiwoom-kospi200-adj-20261009',
    [string]$Holidays = 'C:\AI\trading_system\trading_system\var\backtest\t018-multi\derived-holidays-2016-2023.json',
    [string]$Cutoff = '2026-01-01',
    [string]$FlowSource = ''      # 수급(ka10060) 폴더. 주면 data\flow\ 로만 복사하고 일봉은 건드리지 않는다(dt 열 YYYYMMDD 기준으로 잘라 냄)
)
$ErrorActionPreference = 'Stop'
$lab = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if ($FlowSource -ne '') {
    if (-not (Test-Path $FlowSource)) { throw "수급 원본 폴더 없음: $FlowSource" }
    $destFlow = Join-Path $lab 'data\flow'
    New-Item -ItemType Directory -Force $destFlow | Out-Null
    Get-ChildItem $destFlow -Filter *.csv | Remove-Item -Confirm:$false
    $cutYmd = $Cutoff.Replace('-', '')
    $nf = 0; $cutf = 0
    foreach ($f in Get-ChildItem $FlowSource -Filter *.csv) {
        $lines = Get-Content $f.FullName
        # 운영 파일명이 <코드>-ka10060-amt.csv 꼴이면 <코드>.csv 로 저장
        $name = ($f.BaseName -split '-')[0] + '.csv'
        $keep = @($lines[0]) + @($lines | Select-Object -Skip 1 | Where-Object { ($_ -split ',')[0] -lt $cutYmd })
        $cutf += ($lines.Count - $keep.Count)
        if ($keep.Count -gt 1) { Set-Content -Path (Join-Path $destFlow $name) -Value $keep -Encoding ascii; $nf++ }
    }
    Add-Content -Path (Join-Path $lab 'data\SOURCE.txt') -Value @("flow_source=$FlowSource", "flow_synced=$(Get-Date -Format 'yyyy-MM-dd HH:mm')", "flow_stocks=$nf") -Encoding ascii
    Write-Output "수급 복사 $nf 종목, 잘라 낸 행($Cutoff 이후) $cutf, 위치 $destFlow"
    exit 0
}
$dest = Join-Path $lab 'data\daily'
$destIdx = Join-Path $lab 'data\index'
if (-not (Test-Path $Source)) { throw "원본 폴더 없음: $Source" }
New-Item -ItemType Directory -Force $dest | Out-Null
New-Item -ItemType Directory -Force $destIdx | Out-Null
Get-ChildItem $dest -Filter *.csv | Remove-Item -Confirm:$false
Get-ChildItem $destIdx -Filter *.csv | Remove-Item -Confirm:$false

function Copy-Cut([System.IO.FileInfo]$f, [string]$target) {
    $lines = Get-Content $f.FullName
    $keep = @($lines[0]) + @($lines | Select-Object -Skip 1 | Where-Object { $_.Substring(0, 10) -lt $Cutoff })
    $script:cut += ($lines.Count - $keep.Count)
    if ($keep.Count -le 1) { $script:skipped += $f.BaseName; return $false }
    Set-Content -Path (Join-Path $target $f.Name) -Value $keep -Encoding ascii
    return $true
}

$n = 0; $cut = 0; $skipped = @(); $ni = 0
foreach ($f in Get-ChildItem $Source -Filter *.csv) { if (Copy-Cut $f $dest) { $n++ } }
$idxDir = Join-Path $Source 'index'
if (Test-Path $idxDir) { foreach ($f in Get-ChildItem $idxDir -Filter *.csv) { if (Copy-Cut $f $destIdx) { $ni++ } } }
# KOSPI(001)는 전략의 "국면 입력"으로도 쓴다 → data\daily\KOSPI.csv 로 한 부 더(거래 종목 아님 — 전략이 코드 KOSPI를 거래하지 않도록 짜고,
# 사건 연구 스크립트는 6자리 숫자 코드만 읽는다). 운영 검증 실행기는 폴더 전체를 유니버스로 보므로 전략이 반드시 제외해야 한다.
$k = Join-Path $destIdx '001.csv'
if (Test-Path $k) { Copy-Item $k (Join-Path $dest 'KOSPI.csv') -Force }
if (Test-Path $Holidays) { Copy-Item $Holidays (Join-Path $lab 'data\holidays-2016-2023.json') -Force }
Set-Content -Path (Join-Path $lab 'data\SOURCE.txt') -Value @("source=$Source", "cutoff=$Cutoff", "synced=$(Get-Date -Format 'yyyy-MM-dd HH:mm')", "stocks=$n", "index=$ni", "skipped=$($skipped -join ',')") -Encoding ascii
Write-Output "복사 $n 종목 + 지수 $ni 개, 잘라 낸 행($Cutoff 이후) $cut, 제외(봉 없음) $($skipped.Count)개 [$($skipped -join ', ')], 위치 $dest"

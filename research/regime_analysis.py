"""국면 사후 분석 — 이미 끝난 validate 거래(trades.csv)를 "시장 국면"으로 나눠 거래당 기대값을 비교한다. 전략 수정·재실행 없음.

- 국면 대용 지수: data/daily 30종목 **동일가중 종가 지수**(KOSPI 지수 데이터가 없어서 대용 — 생존편향 포함). 지수 > SMA(200) = 상승 국면.
- 거래의 국면 = 진입일 전일 기준(판정 시점에 알 수 있는 정보만).
- 목적: "추세형 전략이 특정 국면에서만 번다"는 가설을 확인하는 **사후 분석**이다. 이 결과로 필터 파라미터를 고르면 데이터 마이닝이므로,
  여기서는 SMA 200 하나만 사전 고정해 본다(다른 값 시험 안 함).

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\regime_analysis.py
출력: research/<날짜>-regime-analysis.md
"""

from __future__ import annotations

import csv
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SMA_N = 200   # 사전 고정 — 바꾸지 않는다
RUNS = {
    "rs-momentum v1": LAB / "results/20261009-rs_momentum/rs-momentum-v1/runs",
    "rs-momentum v2": LAB / "results/20261010-rs_momentum/rs-momentum-v2/runs",
    "donchian-breakout v1": LAB / "results/20261011-donchian_breakout/donchian-breakout-v1/runs",
    "example-sma v1": LAB / "results/20261009-example_sma/example-sma-v1/runs",
}


def kospi_index() -> dict[date, float] | None:
    """data/index/001.csv(KOSPI, 운영 조회본)가 있으면 실제 지수를 쓴다."""
    f = LAB / "data" / "index" / "001.csv"
    if not f.exists():
        return None
    out: dict[date, float] = {}
    with f.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[date.fromisoformat(r["date"])] = float(r["close"])
    return out


def equal_weight_index() -> dict[date, float]:
    """각 종목 종가를 첫 봉 = 1로 정규화해 날짜별 평균(그날 봉이 있는 종목만). KOSPI 파일이 없을 때의 대용."""
    series: dict[date, list[float]] = {}
    for f in sorted((LAB / "data" / "daily").glob("[0-9]*.csv")):
        base = None
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                c = float(r["close"])
                if base is None:
                    base = c
                series.setdefault(date.fromisoformat(r["date"]), []).append(c / base)
    return {d: statistics.mean(v) for d, v in sorted(series.items())}


def regime_map(idx: dict[date, float]) -> dict[date, bool | None]:
    days = sorted(idx)
    vals = [idx[d] for d in days]
    out: dict[date, bool | None] = {}
    for i, d in enumerate(days):
        if i + 1 < SMA_N:
            out[d] = None
        else:
            out[d] = vals[i] > statistics.mean(vals[i + 1 - SMA_N:i + 1])
    return out


def prev_trading_day(d: date, days_sorted: list[date]) -> date | None:
    lo, hi = 0, len(days_sorted) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if days_sorted[mid] < d:
            best = days_sorted[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def main() -> int:
    real = kospi_index()
    idx = real if real is not None else equal_weight_index()
    idx_name = "KOSPI 지수(운영 조회본 data/index/001.csv)" if real is not None else "유니버스 동일가중 대용 지수"
    reg = regime_map(idx)
    days_sorted = sorted(idx)
    out = [f"# 국면 사후 분석 ({date.today()}) — {idx_name} > SMA({SMA_N}) 기준", "",
           "validate 기본 실행(7창)의 왕복 거래를 진입 전일 국면으로 나눴다. **사후 분석**이며 전략 수정·재실행 없음. 거래 자체는 30종목 생존 유니버스에서 나온 것. "
           "SMA 기간은 200 하나만 사전 고정(다른 값 시험 안 함 — 결과 보고 고르면 데이터 마이닝).", ""]
    up_days = sum(1 for v in reg.values() if v is True)
    known = sum(1 for v in reg.values() if v is not None)
    out.append(f"- 지수 상승 국면 비율(SMA 워밍업 뒤~2025): {up_days}/{known} = {up_days/known:.0%} 거래일")
    out.append("")
    out.append("| 전략 | 국면 | 왕복 | 거래당 기대값(원) | 승률 | 손익 합 |")
    out.append("|---|---|---|---|---|---|")
    for name, run_dir in RUNS.items():
        if not run_dir.exists():
            continue
        buckets: dict[str, list[float]] = {"상승(지수>SMA200)": [], "하락/횡보(지수<=SMA200)": [], "미정(워밍업)": []}
        for k in range(1, 8):
            f = run_dir / f"w{k}-base" / "trades.csv"
            if not f.exists():
                continue
            with f.open(encoding="utf-8-sig") as fh:
                for r in csv.DictReader(fh):
                    if not r["손익"].strip():
                        continue
                    entry_day = datetime.strptime(r["진입일시"][:10], "%Y-%m-%d").date()
                    pd = prev_trading_day(entry_day, days_sorted)
                    state = reg.get(pd) if pd else None
                    key = "미정(워밍업)" if state is None else ("상승(지수>SMA200)" if state else "하락/횡보(지수<=SMA200)")
                    buckets[key].append(float(r["손익"]))
        for key, pnl in buckets.items():
            if not pnl:
                continue
            win = sum(1 for x in pnl if x > 0) / len(pnl)
            out.append(f"| {name} | {key} | {len(pnl)} | {statistics.mean(pnl):,.0f} | {win:.0%} | {sum(pnl):,.0f} |")
    out += ["", "## 읽는 법",
            "- 상승 국면에서만 양수이고 하락/횡보에서 음수면 '국면 필터'가 손실을 걸러 낼 **가능성**이 있다는 뜻이다. 그러나 이 표를 보고 필터를 넣은 전략은 "
            "같은 데이터로 검증하면 안 된다(사후 선택). 필터 전략은 **확장된 데이터(코스피200·KOSPI 지수)** 에서 사전 등록 후 검증한다.",
            "- 하락/횡보 국면의 거래가 적으면(추세형은 그 국면에 신호가 드묾) 비교 자체가 약하다.",
            ("- 지수: 실제 KOSPI(운영 조회본). 거래 표본은 30종목 생존 유니버스 → 하락 국면에서도 양수가 나오는 드리프트 주의." if real is not None
             else "- 생존편향: 대용 지수가 생존 종목 동일가중이라 '상승 국면' 비율이 실제 KOSPI보다 높게 나온다.")]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-regime-analysis.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

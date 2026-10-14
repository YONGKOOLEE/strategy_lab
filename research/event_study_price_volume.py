"""가격·거래량 사건 연구 — 전략 아님. 30종목(확장되면 그대로 재실행)에서 사전 고정 규칙의 사건 뒤 5·20·60거래일 수익 분포.

사건(전일 봉 기준으로 확인, 진입 = 다음 날 시가, 수익 = 종가/진입 − 1, 비용 전, 같은 종목 20거래일 내 중복 제외):
- E1 52주 신고가: 종가 > 직전 250거래일 최고 종가(당일 제외), 전일은 아니었음
- E2 거래량 급증 + 상승: 거래량 ≥ 50일 평균 × 3 AND 종가 상승 ≥ +3%
- E3 갭 상승: 시가 ≥ 전일 종가 × 1.05 (그날 봉 확인 뒤 다음 날 시가 진입)
- E4 거래량 급증 + 하락: 거래량 ≥ 50일 평균 × 3 AND 종가 하락 ≤ −3% (되돌림 가설용)
- E5 20일 신저가: 종가 < 직전 20거래일 최저 종가 (추세 하락 지속 vs 반등 확인용)
규칙·임계는 사전 고정이며 결과를 보고 바꾸지 않는다. 생존편향 포함(모든 수익 과대 추정).

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\event_study_price_volume.py
출력: research/<날짜>-event-study-price-volume.md
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
COST = 0.0043
HORIZONS = (5, 20, 60)
COOLDOWN = 20


def load(path: Path):
    days, o, c, v = [], [], [], []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            days.append(date.fromisoformat(r["date"]))
            o.append(float(r["open"])); c.append(float(r["close"])); v.append(float(r["volume"]))
    return days, o, c, v


def events_for(kind: str, t: int, o, c, v) -> bool:
    if t < 251:
        return False
    if kind == "E1":
        return c[t] > max(c[t - 250:t]) and not (c[t - 1] > max(c[t - 251:t - 1]))
    va = statistics.mean(v[t - 50:t])
    if kind == "E2":
        return v[t] >= 3 * va and c[t] / c[t - 1] - 1 >= 0.03
    if kind == "E3":
        return o[t] >= c[t - 1] * 1.05
    if kind == "E4":
        return v[t] >= 3 * va and c[t] / c[t - 1] - 1 <= -0.03
    if kind == "E5":
        return c[t] < min(c[t - 20:t])
    return False


def dist(vals):
    if not vals:
        return "—"
    med = statistics.median(vals)
    win = sum(1 for x in vals if x > COST) / len(vals)
    return f"평균 {statistics.mean(vals)*100:+.2f}% 중앙 {med*100:+.2f}% 비용 초과 {win:.0%}"


def main() -> int:
    names = {"E1": "52주 신고가", "E2": "거래량 3배 + 상승 3%", "E3": "갭 상승 5%", "E4": "거래량 3배 + 하락 3%", "E5": "20일 신저가"}
    results = {k: {h: [] for h in HORIZONS} for k in names}
    counts: dict[str, Counter] = {k: Counter() for k in names}
    for f in sorted((LAB / "data" / "daily").glob("[0-9]*.csv")):   # 종목 코드만(KOSPI.csv 제외)
        days, o, c, v = load(f)
        last = {k: -10_000 for k in names}
        for t in range(251, len(c) - 61):
            for k in names:
                if t - last[k] < COOLDOWN or not events_for(k, t, o, c, v):
                    continue
                entry = o[t + 1]
                for h in HORIZONS:
                    results[k][h].append(c[t + 1 + h] / entry - 1)
                counts[k][days[t].year] += 1
                last[k] = t
    # 기준선: 모든 거래일(사건 무관) 다음 날 시가 진입 수익 분포 — 유니버스 자체의 드리프트(생존편향)를 재는 자
    base = {h: [] for h in HORIZONS}
    for f in sorted((LAB / "data" / "daily").glob("[0-9]*.csv")):
        days, o, c, v = load(f)
        for t in range(251, len(c) - 61, 5):          # 5일 간격 표본
            for h in HORIZONS:
                base[h].append(c[t + 1 + h] / o[t + 1] - 1)
    n_stocks = len(list((LAB / "data" / "daily").glob("[0-9]*.csv")))
    src = (LAB / "data" / "SOURCE.txt").read_text(encoding="ascii").splitlines()[0] if (LAB / "data" / "SOURCE.txt").exists() else "data/daily"
    out = [f"# 가격·거래량 사건 연구 ({date.today()}) — {n_stocks}종목", "",
           f"전략 아님. {n_stocks}종목 2016~2025({src}), 사건 확인 다음 날 시가 진입, 비용 전, 같은 종목 20거래일 내 중복 제외, 임계 사전 고정. "
           "**생존편향 포함 — 모든 수익은 과대 추정**(현재 구성 종목 = 살아남은 종목).", "",
           "| 사건 | n | +5일 | +20일 | +60일 |", "|---|---|---|---|---|",
           f"| **기준선(모든 날, 5일 간격 표본)** | {len(base[5])} | {dist(base[5])} | {dist(base[20])} | {dist(base[60])} |"]
    for k, nm in names.items():
        n = len(results[k][5])
        out.append(f"| {k} {nm} | {n} | {dist(results[k][5])} | {dist(results[k][20])} | {dist(results[k][60])} |")
    out += ["", "## 연도별 사건 수"]
    for k, nm in names.items():
        out.append(f"- {k} {nm}: {dict(sorted(counts[k].items()))}")
    out += ["", "## 읽는 법(사전)",
            "- '우위 후보'로 볼 조건: n ≥ 200, +20일 중앙 > 비용(0.43%), 비용 초과 비율 > 55%, 연도별로 부호가 뒤집히지 않음. 어느 하나라도 아니면 사건 → 전략화 안 함.",
            "- 이 표에서 좋은 사건을 골라 전략을 만들면 사후 선택이다. 확장 데이터(코스피200)에서 같은 규칙으로 재실행해 재현되는지 먼저 본다.",
            "- **기준선과 비교**: 사건 뒤 수익이 기준선(모든 날)과 비슷하면 사건에 정보가 없고 유니버스 드리프트(생존편향)일 뿐이다. 사건의 가치 = 사건 수익 − 기준선 수익."]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-event-study-price-volume-{n_stocks}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

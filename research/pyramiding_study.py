"""피라미딩 규칙 연구 — research/2026-10-11-pyramiding-study-design.md 사전 등록 그대로. 전략 아님.

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\pyramiding_study.py
출력: research/<날짜>-pyramiding-study-<종목수>.md
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
STEP = 21
MAX_HOLD = 120
COST = 0.0043
RULES = {"P0": [], "P1": [1.0, 2.0], "P2": [2.0, 4.0], "P3": [-1.0]}


def load_all():
    data = {}
    for f in sorted((LAB / "data" / "daily").glob("[0-9]*.csv")):
        d, o, h, l, c = [], [], [], [], []
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                d.append(r["date"]); o.append(float(r["open"])); h.append(float(r["high"])); l.append(float(r["low"])); c.append(float(r["close"]))
        data[f.stem] = (d, o, h, l, c)
    return data


def atr(h, l, c, i, n=14):
    if i - n < 0:
        return None
    return sum(max(h[k] - l[k], abs(h[k] - c[k - 1]), abs(l[k] - c[k - 1])) for k in range(i - n + 1, i + 1)) / n


def simulate(o, h, l, c, ei, levels):
    """ei = 진입일(시가). levels = A0 배수 목록(양수: 위, 음수: 아래). 반환 (자본 사용 기준 수익률, 사용 단위)."""
    a0 = atr(h, l, c, ei - 1)
    if a0 is None or a0 <= 0:
        return None
    entry = o[ei]
    units = [entry]              # 각 단위 매수가
    pending = list(levels)
    peak = c[ei]
    end = min(ei + MAX_HOLD, len(c) - 2)
    k = ei
    exit_price = None
    while k < end:
        peak = max(peak, c[k])
        a = atr(h, l, c, k)
        if a is not None and c[k] < peak - 2 * a:
            exit_price = o[k + 1]; break
        if pending:
            lvl = pending[0]
            hit = (c[k] >= entry + lvl * a0) if lvl > 0 else (c[k] <= entry + lvl * a0)
            if hit and k + 1 < len(o):
                units.append(o[k + 1]); pending.pop(0)
        k += 1
    if exit_price is None:
        exit_price = o[end]
    pnl = sum(exit_price / u - 1 - COST for u in units)   # 단위 금액 1 기준 손익 합
    return pnl / len(units), len(units)                      # 자본 사용(최대 단위 수) 기준


def main() -> int:
    data = load_all()
    days = max((v[0] for v in data.values()), key=len)
    start_idx = next(i for i, d in enumerate(days) if d >= "2017-01-01")
    res = {k: [] for k in RULES}
    units = {k: [] for k in RULES}
    by_year = {k: defaultdict(list) for k in RULES}
    n_dec = 0
    for code, (d, o, h, l, c) in data.items():
        pos = {dd: i for i, dd in enumerate(d)}
        for D in days[start_idx::STEP]:
            i = pos.get(D)
            if i is None or i < 20 or i + MAX_HOLD + 5 >= len(c):
                continue
            ei = i + 1
            row = {}
            for k, lv in RULES.items():
                r = simulate(o, h, l, c, ei, lv)
                if r is None:
                    break
                row[k] = r
            if len(row) < len(RULES):
                continue
            n_dec += 1
            for k, (ret, nu) in row.items():
                res[k].append(ret); units[k].append(nu); by_year[k][D[:4]].append(ret)

    def pct(x):
        return f"{x*100:+.2f}%"

    out = [f"# 피라미딩 규칙 연구 ({date.today()}) — {len(data)}종목, 결정 {n_dec}건", "",
           "사전 등록: research/2026-10-11-pyramiding-study-design.md. E-NOW 진입·X-ATR 청산 공통, 자본 사용(최대 단위) 기준 수익률, 단위마다 비용 0.43% 차감. "
           "전 종목 대리 표본 — 규칙 간 상대 비교만(생존편향 포함).", "",
           "| 규칙 | 평균 | 중앙 | 승률 | 평균 단위 | 최악 10% 평균 | 상위 10% 평균 | P0 대비 평균 | P0 대비 최악 10% |", "|---|---|---|---|---|---|---|---|---|"]
    s0 = sorted(res["P0"]); n10 = max(1, len(s0) // 10)
    w0, m0 = statistics.mean(s0[:n10]), statistics.mean(res["P0"])
    for k, v in res.items():
        s = sorted(v)
        w = statistics.mean(s[:n10])
        out.append(f"| {k} | {pct(statistics.mean(v))} | {pct(statistics.median(v))} | {sum(1 for x in v if x > 0)/len(v):.0%} | {statistics.mean(units[k]):.2f} | "
                   f"{pct(w)} | {pct(statistics.mean(s[-n10:]))} | {(statistics.mean(v)-m0)*100:+.2f}pp | {(w-w0)*100:+.2f}pp |")
    out += ["", "연도별 평균(P0 / P1 / P2 / P3) — P1·P2가 P0보다 높은 해 수:"]
    win1 = win2 = 0
    for y in sorted(by_year["P0"]):
        m = {k: statistics.mean(by_year[k][y]) for k in RULES}
        win1 += m["P1"] > m["P0"]; win2 += m["P2"] > m["P0"]
        out.append(f"- {y}: {pct(m['P0'])} / {pct(m['P1'])} / {pct(m['P2'])} / {pct(m['P3'])}")
    out.append(f"- P1 우세 {win1}/{len(by_year['P0'])}년, P2 우세 {win2}/{len(by_year['P0'])}년")
    out += ["", "## 판정 기준(사전)", "- 가치 있음: P1 또는 P2가 P0 대비 평균 ≥ +0.5pp AND 최악 10% ≥ −0.5pp 이내 AND 연도별 우세 ≥ 6/9.",
            "- P3(물타기): 최악 10%가 P0보다 나쁘면 '손실 중 INCREASE 금지' 근거로 기록."]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-pyramiding-study-{len(data)}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

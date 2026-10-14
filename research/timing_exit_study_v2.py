"""타이밍·청산 연구 v2 — research/2026-10-11-timing-exit-v2-design.md 사전 등록 그대로. 전략 아님.

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\timing_exit_study_v2.py
출력: research/<날짜>-timing-exit-v2-<종목수>.md
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
STEP, MAX_WAIT, H, COST, MAX_HOLD = 21, 40, 60, 0.0043, 120


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


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def pct(x):
    return f"{x*100:+.2f}%"


def exit_sim(o, h, l, c, ei, rule):
    """반환 (수익 비용 차감, 보유일, 손절 종료 여부)."""
    entry = o[ei]
    end = min(ei + MAX_HOLD, len(c) - 2)
    peak = c[ei]
    for k in range(ei, end):
        peak = max(peak, c[k])
        stop_hit = False
        if rule == "X-ATR3":
            a = atr(h, l, c, k)
            stop_hit = a is not None and c[k] < peak - 3 * a
        elif rule == "X-FIX12":
            stop_hit = c[k] < entry * 0.88
        elif rule == "X-SMA20":
            stop_hit = k >= 20 and k > ei and c[k] < statistics.mean(c[k - 19:k + 1])
        elif rule == "X-SMA50":
            stop_hit = k >= 50 and k > ei and c[k] < statistics.mean(c[k - 49:k + 1])
        if stop_hit:
            return o[k + 1] / entry - 1 - COST, k + 1 - ei, True
    return o[end] / entry - 1 - COST, end - ei, False


def main() -> int:
    data = load_all()
    days = max((v[0] for v in data.values()), key=len)
    start_idx = next(i for i, d in enumerate(days) if d >= "2017-01-01")
    t1 = {k: [] for k in ("E-NOW", "E-PULL", "E-HYB")}
    t1y = {k: defaultdict(list) for k in t1}
    rules = ("X-ATR3", "X-FIX12", "X-SMA20", "X-SMA50")
    t2 = {k: [] for k in rules}; t2h = {k: [] for k in rules}; t2s = {k: 0 for k in rules}; t2y = {k: defaultdict(list) for k in rules}
    n_dec = 0
    for code, (d, o, h, l, c) in data.items():
        pos = {dd: i for i, dd in enumerate(d)}
        for D in days[start_idx::STEP]:
            i = pos.get(D)
            if i is None or i < 60 or i + MAX_WAIT + H + MAX_HOLD + 5 >= len(c):
                continue
            n_dec += 1; yr = D[:4]
            # T1-v2
            e_now = i + 1
            e_pull = next((k + 1 for k in range(i + 1, i + MAX_WAIT + 1) if c[k] <= c[i] * 0.95), None)
            e_hyb = e_pull if e_pull is not None else i + MAX_WAIT + 1
            for k, ei in (("E-NOW", e_now), ("E-PULL", e_pull), ("E-HYB", e_hyb)):
                if ei is None:
                    continue
                r = c[ei + H] / o[ei] - 1
                t1[k].append(r); t1y[k][yr].append(r)
            # T2-v2
            for rule in rules:
                r, hold, stop = exit_sim(o, h, l, c, e_now, rule)
                t2[rule].append(r); t2h[rule].append(hold); t2s[rule] += stop; t2y[rule][yr].append(r)

    out = [f"# 타이밍·청산 연구 v2 ({date.today()}) — {len(data)}종목, 결정 {n_dec}건", "",
           "사전 등록: research/2026-10-11-timing-exit-v2-design.md. 전 종목 대리 표본, 규칙 간 상대 비교(생존편향 포함). T1 비용 전, T2 비용 차감.", "",
           "## T1-v2 진입 타이밍 (+60일, 비용 전, 결정당)", "", "| 규칙 | n | 평균 | 중앙 | NOW 대비 중앙 | 연도별 NOW 대비 우세 |", "|---|---|---|---|---|---|"]
    now_med = med(t1["E-NOW"])
    for k, v in t1.items():
        wins = sum(1 for y in t1y["E-NOW"] if y in t1y[k] and med(t1y[k][y]) > med(t1y["E-NOW"][y]))
        out.append(f"| {k} | {len(v)} | {pct(statistics.mean(v))} | {pct(med(v))} | {(med(v)-now_med)*100:+.2f}pp | {wins}/{len(t1y['E-NOW'])} |")
    out += ["", "연도별 중앙(NOW / PULL / HYB):"]
    for y in sorted(t1y["E-NOW"]):
        out.append(f"- {y}: {pct(med(t1y['E-NOW'][y]))} / {pct(med(t1y['E-PULL'].get(y, [])))} / {pct(med(t1y['E-HYB'][y]))}")
    out += ["", "## T2-v2 청산 규칙 (E-NOW 진입, 비용 차감, 최대 120일)", "", "| 규칙 | 평균 | 중앙 | 승률 | 평균 보유일 | 손절 피격률 | 최악 10% | 상위 10% |", "|---|---|---|---|---|---|---|---|"]
    for k in rules:
        v = sorted(t2[k]); n10 = max(1, len(v) // 10)
        out.append(f"| {k} | {pct(statistics.mean(v))} | {pct(med(v))} | {sum(1 for x in v if x > 0)/len(v):.0%} | {statistics.mean(t2h[k]):.0f} | "
                   f"{t2s[k]/len(v):.0%} | {pct(statistics.mean(v[:n10]))} | {pct(statistics.mean(v[-n10:]))} |")
    out += ["", "연도별 중앙(" + " / ".join(rules) + "):"]
    for y in sorted(t2y[rules[0]]):
        out.append(f"- {y}: " + " / ".join(pct(med(t2y[r][y])) for r in rules))
    out += ["", "## 판정 기준(사전)", "- T1-v2: HYB − NOW 중앙 ≥ +0.5pp AND 평균 ≥ NOW AND 연도별 ≥ 6/9 → 채택 후보. 중앙만 좋으면 보수형 옵션.",
            "- T2-v2: 보수형 = 최악 10% 최소, 공격형 = 평균 최대. 손절 피격률 > 50%는 '너무 좁음'."]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-timing-exit-v2-{len(data)}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out)); print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

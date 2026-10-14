"""타이밍(T1)·청산(T2) 규칙 연구 — research/2026-10-11-timing-exit-study-design.md 사전 등록 그대로. 전략 아님.

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\timing_exit_study.py
출력: research/<날짜>-timing-exit-study-<종목수>.md
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
MAX_WAIT = 40
H = 60
COST = 0.0043
SMA_N = 200


def load_all():
    data = {}
    for f in sorted((LAB / "data" / "daily").glob("[0-9]*.csv")):
        d, o, h, l, c = [], [], [], [], []
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                d.append(r["date"]); o.append(float(r["open"])); h.append(float(r["high"])); l.append(float(r["low"])); c.append(float(r["close"]))
        data[f.stem] = (d, o, h, l, c)
    return data


def regime_map():
    p = LAB / "data" / "index" / "001.csv"
    if not p.exists():
        return {}
    ds, cs = [], []
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ds.append(r["date"]); cs.append(float(r["close"]))
    return {d: (None if i + 1 < SMA_N else cs[i] > statistics.mean(cs[i + 1 - SMA_N:i + 1])) for i, d in enumerate(ds)}


def atr(h, l, c, i, n=14):
    if i - n < 0:
        return None
    trs = [max(h[k] - l[k], abs(h[k] - c[k - 1]), abs(l[k] - c[k - 1])) for k in range(i - n + 1, i + 1)]
    return sum(trs) / n


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def pct(x):
    return f"{x*100:+.2f}%"


def main() -> int:
    data = load_all()
    reg = regime_map()
    days = max((v[0] for v in data.values()), key=len)
    start_idx = next(i for i, d in enumerate(days) if d >= "2017-01-01")
    # T1
    t1 = {"E-NOW": [], "E-PULL": [], "E-BRK": []}
    t1_year = {k: defaultdict(list) for k in t1}
    t1_pair = []            # (now, pull, brk) 셋 모두 진입한 쌍
    skipped = {"E-PULL": 0, "E-BRK": 0}
    t1_regime = {k: {"up": [], "down": []} for k in t1}
    # T2
    t2 = {"X-ATR": [], "X-FIX": [], "X-SMA": []}
    t2_hold = {k: [] for k in t2}
    t2_year = {k: defaultdict(list) for k in t2}
    n_dec = 0
    for code, (d, o, h, l, c) in data.items():
        pos = {dd: i for i, dd in enumerate(d)}
        for D in days[start_idx::STEP]:
            i = pos.get(D)
            if i is None or i < 30 or i + MAX_WAIT + H + 125 >= len(c):
                continue
            n_dec += 1
            yr = D[:4]
            state = reg.get(D)
            # --- T1 진입일 찾기 ---
            entries = {}
            entries["E-NOW"] = i + 1
            e_pull = next((k + 1 for k in range(i + 1, i + MAX_WAIT + 1) if c[k] <= c[i] * 0.95), None)
            e_brk = next((k + 1 for k in range(i + 1, i + MAX_WAIT + 1) if c[k] > max(c[k - 20:k])), None)
            entries["E-PULL"], entries["E-BRK"] = e_pull, e_brk
            rets = {}
            for k, ei in entries.items():
                if ei is None:
                    skipped[k] += 1
                    continue
                r = c[ei + H] / o[ei] - 1
                rets[k] = r
                t1[k].append(r); t1_year[k][yr].append(r)
                if state is not None:
                    t1_regime[k]["up" if state else "down"].append(r)
            if len(rets) == 3:
                t1_pair.append((rets["E-NOW"], rets["E-PULL"], rets["E-BRK"]))
            # --- T2: E-NOW 진입 뒤 청산 규칙 ---
            ei = i + 1
            entry = o[ei]
            # X-ATR
            peak = c[ei]; exit_i = None
            for k in range(ei, min(ei + 120, len(c) - 2)):
                peak = max(peak, c[k])
                a = atr(h, l, c, k)
                if a is not None and c[k] < peak - 2 * a:
                    exit_i = k + 1; break
            if exit_i is None:
                exit_i = min(ei + 120, len(c) - 2)
            r = o[exit_i] / entry - 1 - COST
            t2["X-ATR"].append(r); t2_hold["X-ATR"].append(exit_i - ei); t2_year["X-ATR"][yr].append(r)
            # X-FIX
            exit_i = next((k + 1 for k in range(ei, ei + 60) if c[k] < entry * 0.93), ei + 60)
            r = o[exit_i] / entry - 1 - COST
            t2["X-FIX"].append(r); t2_hold["X-FIX"].append(exit_i - ei); t2_year["X-FIX"][yr].append(r)
            # X-SMA
            exit_i = None
            for k in range(ei + 1, min(ei + 120, len(c) - 2)):
                if k >= 20 and c[k] < statistics.mean(c[k - 19:k + 1]):
                    exit_i = k + 1; break
            if exit_i is None:
                exit_i = min(ei + 120, len(c) - 2)
            r = o[exit_i] / entry - 1 - COST
            t2["X-SMA"].append(r); t2_hold["X-SMA"].append(exit_i - ei); t2_year["X-SMA"][yr].append(r)

    out = [f"# 타이밍·청산 규칙 연구 ({date.today()}) — {len(data)}종목, 결정 {n_dec}건", "",
           "사전 등록: research/2026-10-11-timing-exit-study-design.md. 전 종목을 '사람이 사기로 정한 종목'의 대리 표본으로 쓰고 규칙 간 **상대 비교**만 한다. "
           "생존편향 포함(절대 수치 과대). T1은 비용 전, T2는 왕복 비용 0.43% 차감.", ""]
    out += ["## T1 진입 타이밍 (+60거래일 수익, 비용 전)", "", "| 규칙 | 진입 n | 미진입 비율 | 평균 | 중앙 | 상승 국면 중앙 | 하락 국면 중앙 |", "|---|---|---|---|---|---|---|"]
    for k, v in t1.items():
        miss = skipped.get(k, 0) / n_dec if n_dec else 0
        out.append(f"| {k} | {len(v)} | {miss:.0%} | {pct(statistics.mean(v))} | {pct(med(v))} | {pct(med(t1_regime[k]['up']))} | {pct(med(t1_regime[k]['down']))} |")
    if t1_pair:
        now = [a for a, _, _ in t1_pair]; pull = [b for _, b, _ in t1_pair]; brk = [x for _, _, x in t1_pair]
        out += ["", f"페어 비교(셋 모두 진입한 {len(t1_pair)}쌍, 중앙): E-NOW {pct(med(now))} · E-PULL {pct(med(pull))} · E-BRK {pct(med(brk))} → "
                f"PULL−NOW {(med(pull)-med(now))*100:+.2f}pp, BRK−NOW {(med(brk)-med(now))*100:+.2f}pp"]
    out += ["", "연도별 중앙(E-NOW / E-PULL / E-BRK):"]
    for y in sorted(t1_year["E-NOW"]):
        out.append(f"- {y}: {pct(med(t1_year['E-NOW'][y]))} / {pct(med(t1_year['E-PULL'].get(y, [])))} / {pct(med(t1_year['E-BRK'].get(y, [])))}")
    out += ["", "## T2 청산 규칙 (E-NOW 진입, 비용 차감)", "", "| 규칙 | n | 평균 | 중앙 | 승률 | 평균 보유일 | 최악 10% 평균 | 상위 10% 평균 |", "|---|---|---|---|---|---|---|---|"]
    for k, v in t2.items():
        s = sorted(v); n10 = max(1, len(s) // 10)
        out.append(f"| {k} | {len(v)} | {pct(statistics.mean(v))} | {pct(med(v))} | {sum(1 for x in v if x > 0)/len(v):.0%} | {statistics.mean(t2_hold[k]):.0f} | "
                   f"{pct(statistics.mean(s[:n10]))} | {pct(statistics.mean(s[-n10:]))} |")
    out += ["", "연도별 중앙(X-ATR / X-FIX / X-SMA):"]
    for y in sorted(t2_year["X-ATR"]):
        out.append(f"- {y}: {pct(med(t2_year['X-ATR'][y]))} / {pct(med(t2_year['X-FIX'][y]))} / {pct(med(t2_year['X-SMA'][y]))}")
    out += ["", "## 판정 기준(사전)", "- T1: PULL 또는 BRK가 NOW보다 중앙 ≥ +1.0pp AND 연도별 ≥ 6/9 양수 → 타이밍 규칙 가치 있음. 미진입 비율 > 30%면 기회 손실 병기.",
            "- T2: 보수형 = 최악 10% 손실 최소, 공격형 = 평균 최대. 연도별 순위 안정 우선. 중앙 차이 < 0.5pp면 '청산 규칙 무차별'."]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-timing-exit-study-{len(data)}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

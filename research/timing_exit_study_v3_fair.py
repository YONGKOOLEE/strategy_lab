"""청산 규칙 연구 v3 — 보유 기간을 맞춘 공정 기준선. research/2026-10-11-v3-batch-design.md §A 사전 등록 그대로. 전략 아님.

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\timing_exit_study_v3_fair.py
출력: research/<날짜>-timing-exit-v3-fair-<종목수>.md

규칙 정의는 v1(timing_exit_study.py: X-ATR2, X-FIX7/60, X-SMA20)·v2(timing_exit_study_v2.py: X-FIX12/120, X-SMA50) 그대로.
보유일 h = 청산 시가 인덱스 − 진입 시가 인덱스 (v1·v2 공통 정의).

기준선 두 가지(둘 다 비용 0.43% 차감, 같은 진입일·같은 h일 보유·h일째 시가 매도):
- HOLD-SAME : 같은 종목을 그냥 h일 보유 — 규칙 거래와 완전히 같은 거래이므로 초과 수익은 구조적으로 0. 검산용으로만 표시.
- HOLD-UNIV : 같은 진입일(캘린더)·같은 h일을 유니버스 전 종목이 그냥 보유했을 때의 동일가중 평균 수익.
              "그 보유 기간의 드리프트"를 나타내며, 초과 수익 = 규칙 − HOLD-UNIV 로 판정한다(구현 해석, 보고서에 명시).
"""

from __future__ import annotations

import csv
import statistics
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
STEP, MAX_WAIT, H, COST, MAX_HOLD = 21, 40, 60, 0.0043, 120
RULES = ("X-ATR2", "X-FIX7/60", "X-SMA20", "X-FIX12/120", "X-SMA50")


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


def exit_sim(o, h, l, c, ei, rule):
    """반환 (수익 비용 차감, 보유일 h, 손절 종료 여부). v1·v2 정의 그대로."""
    entry = o[ei]
    max_hold = 60 if rule == "X-FIX7/60" else MAX_HOLD
    end = min(ei + max_hold, len(c) - 2)
    peak = c[ei]
    for k in range(ei, end):
        peak = max(peak, c[k])
        stop_hit = False
        if rule == "X-ATR2":
            a = atr(h, l, c, k)
            stop_hit = a is not None and c[k] < peak - 2 * a
        elif rule == "X-FIX7/60":
            stop_hit = c[k] < entry * 0.93
        elif rule == "X-FIX12/120":
            stop_hit = c[k] < entry * 0.88
        elif rule == "X-SMA20":
            stop_hit = k >= 20 and k > ei and c[k] < statistics.mean(c[k - 19:k + 1])
        elif rule == "X-SMA50":
            stop_hit = k >= 50 and k > ei and c[k] < statistics.mean(c[k - 49:k + 1])
        if stop_hit:
            return o[k + 1] / entry - 1 - COST, k + 1 - ei, True
    return o[end] / entry - 1 - COST, end - ei, False


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def pct(x):
    return f"{x*100:+.2f}%"


def tail_means(xs):
    s = sorted(xs); n10 = max(1, len(s) // 10)
    return statistics.mean(s[:n10]), statistics.mean(s[-n10:])


def main() -> int:
    t0 = time.perf_counter()
    data = load_all()
    days = max((v[0] for v in data.values()), key=len)
    start_idx = next(i for i, d in enumerate(days) if d >= "2017-01-01")
    decisions = days[start_idx::STEP]
    pos_map = {code: {dd: i for i, dd in enumerate(v[0])} for code, v in data.items()}

    # 1) 규칙별 거래: (code, D, 수익, h, 손절여부)
    trades = {r: [] for r in RULES}
    n_dec = 0
    for code, (d, o, h, l, c) in data.items():
        pos = pos_map[code]
        for D in decisions:
            i = pos.get(D)
            if i is None or i < 60 or i + MAX_WAIT + H + MAX_HOLD + 5 >= len(c):
                continue
            n_dec += 1
            ei = i + 1
            for rule in RULES:
                r, hold, stop = exit_sim(o, h, l, c, ei, rule)
                trades[rule].append((code, D, r, hold, stop))

    # 2) HOLD-UNIV 기준선: (D, h) → 유니버스 동일가중 평균 h일 보유 수익(비용 차감)
    univ_cache: dict[tuple[str, int], float] = {}

    def hold_univ(D: str, hold: int) -> float:
        key = (D, hold)
        if key in univ_cache:
            return univ_cache[key]
        rets = []
        for code, (d, o, h, l, c) in data.items():
            i = pos_map[code].get(D)
            if i is None or i < 60 or i + MAX_WAIT + H + MAX_HOLD + 5 >= len(c):
                continue
            ei = i + 1
            rets.append(o[ei + hold] / o[ei] - 1 - COST)
        v = statistics.mean(rets)
        univ_cache[key] = v
        return v

    # 3) 초과 수익
    excess = {r: [] for r in RULES}          # 규칙 − HOLD-UNIV
    excess_same = {r: [] for r in RULES}     # 규칙 − HOLD-SAME (검산, 0)
    excess_year = {r: defaultdict(list) for r in RULES}
    rule_ret = {r: [] for r in RULES}
    rule_hold = {r: [] for r in RULES}
    rule_stop = {r: 0 for r in RULES}
    excess_stop = {r: {"stop": [], "timeout": []} for r in RULES}
    for rule in RULES:
        for code, D, r, hold, stop in trades[rule]:
            d, o, h, l, c = data[code]
            ei = pos_map[code][D] + 1
            same = o[ei + hold] / o[ei] - 1 - COST
            univ = hold_univ(D, hold)
            ex = r - univ
            excess[rule].append(ex); excess_same[rule].append(r - same); excess_year[rule][D[:4]].append(ex)
            rule_ret[rule].append(r); rule_hold[rule].append(hold); rule_stop[rule] += stop
            excess_stop[rule]["stop" if stop else "timeout"].append(ex)

    elapsed = time.perf_counter() - t0
    years = sorted({D[:4] for D in decisions if any(D[:4] in excess_year[r] for r in RULES)})

    out = [f"# 청산 규칙 연구 v3 — 보유 기간을 맞춘 공정 기준선 ({date.today()}) — {len(data)}종목, 결정 {n_dec}건", "",
           "사전 등록: research/2026-10-11-v3-batch-design.md §A. 규칙 정의 v1(X-ATR2·X-FIX7/60·X-SMA20)·v2(X-FIX12/120·X-SMA50) 그대로. "
           "결정일 D 2017-01~ 21거래일 간격, 진입 D+1 시가, 청산 시가, 왕복 비용 0.43% 차감.",
           "**생존편향 포함(현재 생존 종목 구성, 절대 수치 과대) — 규칙 간 상대 비교만.**", "",
           "## 기준선 정의(구현 해석)",
           "- 거래별 보유일 h = 청산 시가 인덱스 − 진입 시가 인덱스(v1·v2 공통).",
           "- HOLD-SAME: 같은 종목·같은 진입일·같은 h일 보유 후 h일째 시가 매도(비용 차감). 규칙 거래와 **동일한 거래**이므로 초과 수익은 구조적으로 0 — 검산 열로만 표시.",
           "- HOLD-UNIV: 같은 진입일·같은 h일을 유니버스 전 종목(해당일 결정 가능 종목)이 그냥 보유했을 때의 동일가중 평균 수익(비용 차감). "
           "'그 보유 기간의 드리프트'를 뜻하며, **초과 수익 = 규칙 수익 − HOLD-UNIV** 로 판정한다.", "",
           "## 규칙별 초과 수익 (규칙 − HOLD-UNIV, 거래당)", "",
           "| 규칙 | n | 초과 평균 | 초과 중앙 | 초과 최악 10% 평균 | 초과 상위 10% 평균 | 손절 거래 초과 평균 | 기간만료 거래 초과 평균 | 검산 규칙−HOLD-SAME 평균 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in RULES:
        v = excess[r]; lo, hi = tail_means(v)
        st, to = excess_stop[r]["stop"], excess_stop[r]["timeout"]
        out.append(f"| {r} | {len(v)} | {pct(statistics.mean(v))} | {pct(med(v))} | {pct(lo)} | {pct(hi)} | "
                   f"{pct(statistics.mean(st)) if st else 'n/a'} ({len(st)}) | {pct(statistics.mean(to)) if to else 'n/a'} ({len(to)}) | "
                   f"{pct(statistics.mean(excess_same[r]))} |")
    out += ["", "## 연도별 초과 수익 평균 (규칙 − HOLD-UNIV)", "", "| 연도 | " + " | ".join(RULES) + " |", "|---|" + "---|" * len(RULES)]
    for y in years:
        out.append(f"| {y} | " + " | ".join(pct(statistics.mean(excess_year[r][y])) if excess_year[r].get(y) else "n/a" for r in RULES) + " |")
    out.append("| 양수 연도 수 | " + " | ".join(f"{sum(1 for y in years if excess_year[r].get(y) and statistics.mean(excess_year[r][y]) > 0)}/{len(years)}" for r in RULES) + " |")
    out += ["", "## 규칙 수익 자체 (참고, 비용 차감 — v2 표와 같은 정의)", "",
            "| 규칙 | n | 평균 | 중앙 | 승률 | 평균 보유일 | 중앙 보유일 | 손절 피격률 | 최악 10% 평균 | 상위 10% 평균 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in RULES:
        v = rule_ret[r]; lo, hi = tail_means(v)
        out.append(f"| {r} | {len(v)} | {pct(statistics.mean(v))} | {pct(med(v))} | {sum(1 for x in v if x > 0)/len(v):.0%} | "
                   f"{statistics.mean(rule_hold[r]):.0f} | {med(rule_hold[r]):.0f} | {rule_stop[r]/len(v):.0%} | {pct(lo)} | {pct(hi)} |")
    out += ["", "## 참고: 보유 기간 드리프트(HOLD-UNIV를 규칙별 h 분포로 평균)", "",
            "| 규칙 | 규칙 평균 | HOLD-UNIV 평균(같은 h 분포) | 차이 = 초과 평균 |", "|---|---|---|---|"]
    for r in RULES:
        rm = statistics.mean(rule_ret[r]); um = rm - statistics.mean(excess[r])
        out.append(f"| {r} | {pct(rm)} | {pct(um)} | {(rm-um)*100:+.2f}pp |")

    positive = [r for r in RULES if statistics.mean(excess[r]) > 0]
    out += ["", "## 판정 기준(사전, 설계 §A)",
            "- 초과 수익 평균이 **양수인 규칙만** '청산 규칙이 가치를 더한다'로 기록.",
            "- 전부 음수/0이면 '청산 규칙은 보유 기간 선택일 뿐'.",
            "- 보수형·공격형 선택은 v2 판정을 유지하고 이 결과를 병기.", "",
            "## 판정"]
    if positive:
        out.append("- 초과 수익 평균 양수(청산 규칙이 가치를 더한다): " + ", ".join(f"{r} ({pct(statistics.mean(excess[r]))})" for r in positive))
        neg = [r for r in RULES if r not in positive]
        if neg:
            out.append("- 초과 수익 평균 ≤ 0: " + ", ".join(f"{r} ({pct(statistics.mean(excess[r]))})" for r in neg))
    else:
        out.append("- 모든 규칙의 초과 수익 평균 ≤ 0 → **청산 규칙은 보유 기간 선택일 뿐**. "
                   + ", ".join(f"{r} {pct(statistics.mean(excess[r]))}" for r in RULES))
    out += ["", "## 한계",
            "- 생존편향(사후 선택 생존 종목), 수정주가 반올림, 호가 표·VI·거래정지 이력 미반영, 장중 손절 없음, 비용 가정(수수료 0.015%·매도세 0.20%·슬리피지 0.1%).",
            "- HOLD-UNIV는 같은 h를 유니버스가 보유한 평균이므로 초과 수익은 '규칙이 고른 종목·시점의 상대 성과'를 포함한다(종목 선택 효과와 청산 효과를 완전히 분리하지 못함).",
            "- 기간만료 거래의 초과 수익은 청산 규칙과 무관한 종목 상대 성과다. 손절 거래 열을 함께 볼 것.",
            f"- 실행 시간 {elapsed:.1f}초."]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-timing-exit-v3-fair-{len(data)}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out)); print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

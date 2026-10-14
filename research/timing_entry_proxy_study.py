"""T1-v3 진입 타이밍 연구 — 눌림 혼합 진입(E-HYB)의 무상태 근사(E-PROXY).
사전 등록: research/2026-10-11-v3-batch-design.md §B 그대로. 전략 아님.

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\timing_entry_proxy_study.py
출력: research/<날짜>-timing-entry-proxy-<종목수>.md

규칙(결정일 D = 인덱스 i, D 종가 c[i]까지 확정. 체결은 다음 날 시가 — v2와 같은 관례):
- E-NOW   : o[i+1]
- E-HYB   : k∈[i+1, i+40] 중 c[k] ≤ c[i]×0.95 첫 날 → o[k+1]. 없으면 o[i+41]
- E-PROXY : k∈[i, i+40] 중 c[k] ≤ max(c[k-39..k])×0.95 첫 날 → o[k+1]. 없으면 o[i+41]
            (k=i 충족이면 D+1 시가 즉시 진입 = E-NOW와 동일 체결)
수익 = c[ei+60] / o[ei] − 1 (비용 전, 결정당).
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
STEP, MAX_WAIT, H, LOOKBACK, PULL = 21, 40, 60, 40, 0.95
RULES = ("E-NOW", "E-HYB", "E-PROXY")


def load_all():
    data = {}
    for f in sorted((LAB / "data" / "daily").glob("[0-9]*.csv")):
        d, o, c = [], [], []
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                d.append(r["date"]); o.append(float(r["open"])); c.append(float(r["close"]))
        data[f.stem] = (d, o, c)
    return data


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def pct(x):
    return f"{x*100:+.2f}%"


def entry_hyb(c, i):
    k = next((k for k in range(i + 1, i + MAX_WAIT + 1) if c[k] <= c[i] * PULL), None)
    return (k + 1) if k is not None else i + MAX_WAIT + 1


def pulled_back(c, k):
    return c[k] <= max(c[k - LOOKBACK + 1:k + 1]) * PULL


def entry_proxy(c, i):
    k = next((k for k in range(i, i + MAX_WAIT + 1) if pulled_back(c, k)), None)
    return (k + 1) if k is not None else i + MAX_WAIT + 1


def main() -> int:
    t0 = time.perf_counter()
    data = load_all()
    days = max((v[0] for v in data.values()), key=len)
    start_idx = next(i for i, d in enumerate(days) if d >= "2017-01-01")
    res = {k: [] for k in RULES}
    resy = {k: defaultdict(list) for k in RULES}
    n_dec = n_immediate = 0
    wait_proxy, wait_hyb = [], []
    for code, (d, o, c) in data.items():
        pos = {dd: i for i, dd in enumerate(d)}
        for D in days[start_idx::STEP]:
            i = pos.get(D)
            if i is None or i < 60 or i + MAX_WAIT + 1 + H >= len(c):
                continue
            n_dec += 1; yr = D[:4]
            e_now, e_hyb, e_proxy = i + 1, entry_hyb(c, i), entry_proxy(c, i)
            n_immediate += e_proxy == e_now
            wait_proxy.append(e_proxy - e_now); wait_hyb.append(e_hyb - e_now)
            for k, ei in zip(RULES, (e_now, e_hyb, e_proxy)):
                r = c[ei + H] / o[ei] - 1
                res[k].append(r); resy[k][yr].append(r)

    years = sorted(resy["E-NOW"])
    now_med, now_mean = med(res["E-NOW"]), statistics.mean(res["E-NOW"])
    wins = {}
    out = [f"# T1-v3 진입 타이밍 근사 연구 ({date.today()}) — {len(data)}종목, 결정 {n_dec}건", "",
           "사전 등록(설계 참조): research/2026-10-11-v3-batch-design.md §B. 임계·규칙 변경 없음.",
           "생존편향 포함(현재 구성 종목, 과대 추정) — 규칙 간 상대 비교만. 비용 전, 결정당(21거래일 간격, D 2017-01~).",
           "E-HYB 정의는 v2(research/timing_exit_study_v2.py)와 동일. 호가·VI·거래정지 미반영, 09:30 시가 체결 가정.", "",
           "## 규칙별 (+60거래일 수익, 비용 전)", "",
           "| 규칙 | n | 평균 | 중앙 | NOW 대비 중앙 | NOW 대비 평균 | 연도별 NOW 대비 우세 |", "|---|---|---|---|---|---|---|"]
    for k in RULES:
        v = res[k]
        wins[k] = sum(1 for y in years if med(resy[k][y]) > med(resy["E-NOW"][y]))
        out.append(f"| {k} | {len(v)} | {pct(statistics.mean(v))} | {pct(med(v))} | {(med(v)-now_med)*100:+.2f}pp | "
                   f"{(statistics.mean(v)-now_mean)*100:+.2f}pp | {wins[k]}/{len(years)} |")
    out += ["", "## 연도별 중앙 (NOW / HYB / PROXY, 괄호 = PROXY − NOW pp)", "", "| 연도 | n | E-NOW | E-HYB | E-PROXY | PROXY − NOW |", "|---|---|---|---|---|---|"]
    for y in years:
        a, b, p = med(resy["E-NOW"][y]), med(resy["E-HYB"][y]), med(resy["E-PROXY"][y])
        out.append(f"| {y} | {len(resy['E-NOW'][y])} | {pct(a)} | {pct(b)} | {pct(p)} | {(p-a)*100:+.2f}pp |")
    diff_ph = (med(res["E-PROXY"]) - med(res["E-HYB"])) * 100
    imm = n_immediate / n_dec
    out += ["", "## E-PROXY 특성", "",
            f"- E-PROXY − E-HYB 중앙 차이: {diff_ph:+.2f}pp (평균 차이 {(statistics.mean(res['E-PROXY'])-statistics.mean(res['E-HYB']))*100:+.2f}pp)",
            f"- E-PROXY가 D+1에 즉시 진입한 비율: {imm:.1%} ({n_immediate}/{n_dec})",
            f"- 평균 대기 거래일(D+1 기준): E-PROXY {statistics.mean(wait_proxy):.1f}일, E-HYB {statistics.mean(wait_hyb):.1f}일; "
            f"40일 내 미충족→D+41 진입 비율: E-PROXY {sum(1 for w in wait_proxy if w == MAX_WAIT)/n_dec:.1%}, E-HYB {sum(1 for w in wait_hyb if w == MAX_WAIT)/n_dec:.1%}"]
    # 판정 (설계 §B 고정)
    p_med = (med(res["E-PROXY"]) - now_med) * 100
    p_mean_ok = statistics.mean(res["E-PROXY"]) >= now_mean
    c1, c2, c3 = p_med >= 0.5, p_mean_ok, wins["E-PROXY"] >= 6
    adopt = c1 and c2 and c3
    loss = diff_ph <= -0.3
    out += ["", "## 판정 (설계 §B 기준, 사전 고정)", "",
            "기준: E-PROXY − E-NOW 중앙 ≥ +0.5pp AND 평균 ≥ E-NOW AND 연도별 우세 ≥ 6/9 → 채택. E-HYB보다 중앙 0.3pp 이상 낮으면 '근사 손실 있음' 병기.", "",
            f"- 중앙 차이 {p_med:+.2f}pp ≥ +0.5pp: {'충족' if c1 else '미충족'}",
            f"- 평균 ≥ E-NOW: {'충족' if c2 else '미충족'}",
            f"- 연도별 우세 {wins['E-PROXY']}/{len(years)} ≥ 6/9: {'충족' if c3 else '미충족'}",
            f"- 근사 손실(PROXY − HYB 중앙 {diff_ph:+.2f}pp ≤ −0.3pp): {'있음' if loss else '없음'}", "",
            f"**판정: {'채택 — 전략에 넣을 수 있는 근사' if adopt else '미채택 — E-PROXY는 E-NOW 대비 사전 기준 미달'}"
            f"{' (근사 손실 있음 병기)' if loss else ''}**", "",
            "한계: 생존편향(사후 선택 종목), 수정주가 반올림, 호가 표·VI·거래정지 이력 미반영, 장중 손절 없음, 비용 미차감(규칙 간 체결 횟수 동일하므로 상대 비교에 영향 없음).",
            f"실행 시간 {time.perf_counter()-t0:.1f}초."]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-timing-entry-proxy-{len(data)}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out)); print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""수급(투자자별 순매수) 사건 연구 — research/2026-10-11-investor-flow-study-design.md §1~§3을 그대로 구현. 전략 아님.

입력: data/flow/<종목코드>.csv (운영 ka10060 조회본: dt, acc_trde_prica(거래대금 백만원), ind_invsr, frgnr_invsr, orgn, … 백만원 순매수),
     data/daily/<종목코드>.csv (수정주가 일봉 — 가격은 여기서만), data/index/001.csv (KOSPI, 국면 분리).
사건은 전일(t)까지의 수급으로 확인, 진입 = t+1 시가, 수익 = t+1+h 종가 / 진입 − 1 (비용 전), 같은 종목 20거래일 내 중복 제외.
임계는 설계 문서의 사전 고정값. 결과를 보고 바꾸지 않는다.

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\event_study_flow.py
출력: research/<날짜>-event-study-flow-<종목수>.md
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
COST = 0.0043
HORIZONS = (5, 20, 60)
COOLDOWN = 20
SMA_N = 200

# 사전 고정 임계 (설계 §2)
F1 = {"days": 15, "ratio": 0.02}          # 외국인 20일 중 순매수일 ≥ 15 AND 20일 순매수합/거래대금합 ≥ 2%
F1_ALT = {"days": 12, "ratio": 0.01}      # 사전 지정 민감도 1개
F2 = {"days": 15, "ratio": 0.02}          # 기관계
F3 = {"ratio": 0.05, "ret": 0.10}         # 개인 5일 순매수합/거래대금합 ≥ 5% AND 5일 수익률 ≥ +10%
F4 = {"days": 15}                         # 외국인·기관계 20일 중 순매도일 ≥ 15 둘 다

NAMES = {"F1": "외국인 순매수 지속(15일·2%)", "F1a": "외국인 순매수 지속(민감도 12일·1%)", "F2": "기관계 순매수 지속(15일·2%)",
         "F3": "개인 순매수 급증 + 5일 +10%", "F4": "외국인·기관 동시 순매도 지속(15일)"}


def load_daily(code: str):
    p = LAB / "data" / "daily" / f"{code}.csv"
    if not p.exists():
        return None
    d, o, c = [], [], []
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d.append(r["date"].replace("-", "")); o.append(float(r["open"])); c.append(float(r["close"]))
    return d, o, c


def load_flow(p: Path):
    out = {}
    with p.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[r["dt"]] = {"amt": float(r["acc_trde_prica"]), "ind": float(r["ind_invsr"]), "frg": float(r["frgnr_invsr"]), "org": float(r["orgn"])}
    return out


def load_regime():
    p = LAB / "data" / "index" / "001.csv"
    if not p.exists():
        return {}
    ds, cs = [], []
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ds.append(r["date"].replace("-", "")); cs.append(float(r["close"]))
    reg = {}
    for i, d in enumerate(ds):
        reg[d] = None if i + 1 < SMA_N else cs[i] > statistics.mean(cs[i + 1 - SMA_N:i + 1])
    return reg


def main() -> int:
    flow_dir = LAB / "data" / "flow"
    files = sorted(flow_dir.glob("[0-9]*.csv"))
    if not files:
        print(f"data/flow 에 수급 CSV가 없음 — tools\\sync-data.ps1 -FlowSource <운영 폴더> 먼저")
        return 2
    reg = load_regime()
    res = {k: {h: [] for h in HORIZONS} for k in NAMES}
    by_year = {k: defaultdict(list) for k in NAMES}
    by_reg = {k: {"up": [], "down": []} for k in NAMES}
    counts = {k: Counter() for k in NAMES}
    base = {h: [] for h in HORIZONS}
    base_year = defaultdict(list)
    base_prior = []                     # (직전 20일 수익률, +20일 수익률) — 조건부 기준선용(설계 §7)
    ev_prior = {k: [] for k in NAMES}   # 사건의 (직전 20일 수익률, +20일 수익률)
    n_stocks = 0
    for fp in files:
        code = fp.stem
        daily = load_daily(code)
        if daily is None:
            continue
        d, o, c = daily
        flow = load_flow(fp)
        n_stocks += 1
        idx = {day: i for i, day in enumerate(d)}
        last = {k: -10_000 for k in NAMES}
        for t in range(260, len(d) - 61):
            day = d[t]
            if t % 5 == 0:
                for h in HORIZONS:
                    base[h].append(c[t + 1 + h] / o[t + 1] - 1)
                base_year[day[:4]].append(c[t + 21] / o[t + 1] - 1)
                base_prior.append((c[t] / c[t - 20] - 1, c[t + 21] / o[t + 1] - 1))
            win20 = [flow.get(x) for x in d[t - 19:t + 1]]
            win5 = [flow.get(x) for x in d[t - 4:t + 1]]
            prev20 = [flow.get(x) for x in d[t - 20:t]]
            if any(w is None for w in win20) or any(w is None for w in prev20):
                continue
            amt20 = sum(w["amt"] for w in win20) or 1.0
            amt5 = sum(w["amt"] for w in win5) or 1.0

            def cond_f1(ws, p):
                return sum(1 for w in ws if w["frg"] > 0) >= p["days"] and sum(w["frg"] for w in ws) / (sum(w["amt"] for w in ws) or 1.0) >= p["ratio"]

            def cond_f2(ws, p):
                return sum(1 for w in ws if w["org"] > 0) >= p["days"] and sum(w["org"] for w in ws) / (sum(w["amt"] for w in ws) or 1.0) >= p["ratio"]

            hits = {
                "F1": cond_f1(win20, F1) and not cond_f1(prev20, F1),
                "F1a": cond_f1(win20, F1_ALT) and not cond_f1(prev20, F1_ALT),
                "F2": cond_f2(win20, F2) and not cond_f2(prev20, F2),
                "F3": sum(w["ind"] for w in win5) / amt5 >= F3["ratio"] and c[t] / c[t - 5] - 1 >= F3["ret"],
                "F4": sum(1 for w in win20 if w["frg"] < 0) >= F4["days"] and sum(1 for w in win20 if w["org"] < 0) >= F4["days"]
                      and not (sum(1 for w in prev20 if w["frg"] < 0) >= F4["days"] and sum(1 for w in prev20 if w["org"] < 0) >= F4["days"]),
            }
            for k, hit in hits.items():
                if not hit or t - last[k] < COOLDOWN:
                    continue
                entry = o[t + 1]
                r20 = c[t + 21] / entry - 1
                for h in HORIZONS:
                    res[k][h].append(c[t + 1 + h] / entry - 1)
                by_year[k][day[:4]].append(r20)
                ev_prior[k].append((c[t] / c[t - 20] - 1, r20))
                state = reg.get(day)
                if state is not None:
                    by_reg[k]["up" if state else "down"].append(r20)
                counts[k][day[:4]] += 1
                last[k] = t

    def dist(vals):
        if not vals:
            return "—"
        return f"n={len(vals)} 평균 {statistics.mean(vals)*100:+.2f}% 중앙 {statistics.median(vals)*100:+.2f}% 비용초과 {sum(1 for x in vals if x > COST)/len(vals):.0%}"

    def med(vals):
        return statistics.median(vals) if vals else None

    out = [f"# 수급 사건 연구 ({date.today()}) — {n_stocks}종목", "",
           "설계: research/2026-10-11-investor-flow-study-design.md (사전 고정). 전략 아님. 진입 = 사건 확인 다음 날 시가, 비용 전, 같은 종목 20거래일 내 중복 제외. "
           "**생존편향 포함(현재 구성 종목) — 과대 추정.** 사건의 가치 = 사건 수익 − 기준선.", "",
           "| 사건 | +5일 | +20일 | +60일 |", "|---|---|---|---|",
           f"| **기준선(모든 날, 5일 간격)** | {dist(base[5])} | {dist(base[20])} | {dist(base[60])} |"]
    for k, nm in NAMES.items():
        out.append(f"| {k} {nm} | {dist(res[k][5])} | {dist(res[k][20])} | {dist(res[k][60])} |")
    b20 = med(base[20]) or 0.0
    out += ["", "## 판정(사전 기준: n ≥ 200, +20일 중앙 − 기준선 ≥ +0.5pp, 비용 초과 ≥ 55%, 연도별 기준선 대비 양수 ≥ 5/7(2019~2025), 국면 양쪽 부호 같음)", "",
            "| 사건 | n | 중앙−기준선 | 비용초과 | 연도별 양수(2019~25) | 상승국면 중앙 | 하락국면 중앙 | 판정 |", "|---|---|---|---|---|---|---|---|"]
    for k, nm in NAMES.items():
        v = res[k][20]
        if not v:
            out.append(f"| {k} | 0 | — | — | — | — | — | 사건 없음 |"); continue
        m = statistics.median(v) - b20
        win = sum(1 for x in v if x > COST) / len(v)
        yrs = [y for y in map(str, range(2019, 2026)) if by_year[k].get(y) and base_year.get(y)]
        pos = sum(1 for y in yrs if statistics.median(by_year[k][y]) > statistics.median(base_year[y]))
        up, down = med(by_reg[k]["up"]), med(by_reg[k]["down"])
        same_sign = (up is not None and down is not None and (up > 0) == (down > 0))
        ok = len(v) >= 200 and m >= 0.005 and win >= 0.55 and pos >= 5 and same_sign
        out.append(f"| {k} | {len(v)} | {m*100:+.2f}pp | {win:.0%} | {pos}/{len(yrs)} | {'—' if up is None else f'{up*100:+.2f}%'} | "
                   f"{'—' if down is None else f'{down*100:+.2f}%'} | {'**우위 후보**' if ok else '미달'} |")
    # 설계 §7 진단: 직전 20일 수익률 10분위로 맞춘 조건부 기준선
    out += ["", "## 진단(설계 §7): 선행 20일 수익률 조건부 기준선 — 수급 고유 정보 vs 가격 추종", "",
            "| 사건 | 사건 선행 20일 수익률 중앙 | 사건 +20일 중앙 | 조건부 기준선 +20일 중앙(같은 선행 수익률 분위 가중) | 차이 | 해석 |", "|---|---|---|---|---|---|"]
    if base_prior:
        bp_sorted = sorted(base_prior, key=lambda x: x[0])
        n = len(bp_sorted)
        edges = [bp_sorted[int(n * q / 10)][0] for q in range(1, 10)]
        dec_med = []
        for q in range(10):
            lo = -1e9 if q == 0 else edges[q - 1]
            hi = 1e9 if q == 9 else edges[q]
            vals = [y for x, y in bp_sorted if lo <= x < hi]
            dec_med.append(statistics.median(vals) if vals else 0.0)

        def decile(x):
            return sum(1 for e in edges if x >= e)
        for k, nm in NAMES.items():
            ep = ev_prior[k]
            if not ep:
                continue
            prior_med = statistics.median(x for x, _ in ep)
            ev_med = statistics.median(y for _, y in ep)
            cond = statistics.median(dec_med[decile(x)] for x, _ in ep)
            diff = ev_med - cond
            interp = "수급 고유 정보 가능" if diff > 0.005 else ("가격 추종으로 설명됨" if abs(diff) <= 0.005 else "기준선보다 나쁨")
            out.append(f"| {k} | {prior_med*100:+.2f}% | {ev_med*100:+.2f}% | {cond*100:+.2f}% | {diff*100:+.2f}pp | {interp} |")
    out += ["", "## 연도별 사건 수"]
    for k, nm in NAMES.items():
        out.append(f"- {k} {nm}: {dict(sorted(counts[k].items()))}")
    out += ["", "## 연도별 +20일 중앙(사건 / 기준선)"]
    for k in NAMES:
        parts = [f"{y}: {statistics.median(by_year[k][y])*100:+.1f}/{statistics.median(base_year[y])*100:+.1f}" for y in sorted(by_year[k]) if base_year.get(y)]
        out.append(f"- {k}: " + ", ".join(parts))
    out += ["", "## 한계", "- 생존편향(현재 코스피200), 비용 전, 09:30 시가 체결 가정, 수급은 전일 확정값 가정(잠정/확정 차이 미확인), 2018 액면분할 등 0값 날은 조건에 그대로 포함."]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-event-study-flow-{n_stocks}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out[:40]))
    print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""DD. N=5 연간 갱신판 사전 판정표 — 7창(2019~2025 각 1년). 사전 등록: research/2026-10-18-overnight-design.md DD (08:09)."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from crypto_annual_universe import UNI, load_all, lists_for, qv_by_year, simulate  # noqa: E402

data = load_all()
qv = qv_by_year(UNI, list(data))
WIN = [(date(y, 1, 1), date(y, 12, 31)) for y in range(2019, 2026)]
VAR = {"base": {}, "slip0.2%": {"slip": 0.002}, "entry_n=20": {"entry_n": 20}, "entry_n=30": {"entry_n": 30}, "exit_n=40": {"exit_n": 40},
       "exit_n=60": {"exit_n": 60}, "stop_atr=1.6": {"stop_atr": 1.6}, "stop_atr=2.4": {"stop_atr": 2.4}, "risk=4%": {"risk_tot": 0.04},
       "risk=6%": {"risk_tot": 0.06}, "cap=0.784": {"cap_tot": 0.784}, "cap=1.0": {"cap_tot": 1.0}}


def run(n: int, kw: dict) -> list[dict]:
    lists = lists_for(n, data, qv)
    out = []
    for s, e in WIN:
        r = simulate(data, lists, n, s, e, **kw)
        out.append({"year": s.year, "n": len(r["pnls"]), "pnl": sum(r["pnls"]), "ret": r["ret"], "mdd": r["mdd"]})
    return out


def agg(ws: list[dict], yrs: range = range(2019, 2026)) -> tuple[int, float]:
    sel = [w for w in ws if w["year"] in yrs]
    k = sum(w["n"] for w in sel)
    return k, sum(w["pnl"] for w in sel) / k if k else float("nan")


T = {name: run(5, kw) for name, kw in VAR.items()}
print("DD. N=5 연간 갱신판 사전 판정표(7창, 일봉 v1 한 계좌) · 판정 아님(과대 추정 가능)")
for name, ws in T.items():
    k, ev = agg(ws)
    print(f"  {name:13s} 거래 {k:3d}(6창 {agg(ws, range(2020, 2026))[0]:3d}) · 거래당 {ev:+8.1f} USDT · 손실 창 {sum(1 for w in ws if w['ret'] < 0)}/7")
print("  창별(base): " + " · ".join(f"{w['year']} {w['ret']:+.0%}·MDD {w['mdd']:.0%}({w['n']})" for w in T["base"]))
for n in (4, 6):
    ws = run(n, {})
    k, ev = agg(ws)
    print(f"  (이웃 정보) N={n}: 거래 {k} · 거래당 {ev:+.1f} · 손실 창 {sum(1 for w in ws if w['ret'] < 0)}/7 · 창별 " + " ".join(f"{w['ret']:+.0%}" for w in ws))
k7, k6 = agg(T["base"])[0], agg(T["base"], range(2020, 2026))[0]
c3 = agg(T["slip0.2%"])[1] > 0
c4 = all(agg(T[x])[1] > 0 for x in T if x not in ("base", "slip0.2%"))
print(f"  C-2 7창 {k7}·6창 {k6} ({'충족' if k7 >= 100 else '미달'}/{'충족' if k6 >= 100 else '미달'}) · C-3 {'충족' if c3 else '미충족'} · C-4 {'충족' if c4 else '미충족'}")
print(f"  사전 기준: {'v3 후보 유지(일봉판)' if c3 and c4 else '폐기'}")
(LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-annual-preverdict.json").write_text(json.dumps({"table": T, "C2": [k7, k6], "C3": c3, "C4": c4}, ensure_ascii=False, indent=1), encoding="utf-8")

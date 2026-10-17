"""P. crypto-trend v1 strategy.py 사전 판정표 — 1시간 재생(research/crypto_trend_replay.py), 7창. 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md P.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from crypto_trend_replay import base_params, replay  # noqa: E402

SYMS = ["BTCUSDT", "ETHUSDT"]
SKIP = frozenset({0}) if "--ops23" in sys.argv else frozenset()   # Q 후속: 운영 23회 일정(00:00 판정 없음)
WIN = [(date(y, 1, 1), date(y, 12, 31)) for y in range(2019, 2026)]
VAR = [("entry_n", 20), ("entry_n", 30), ("exit_n", 40), ("exit_n", 60), ("stop_atr", "1.6"), ("stop_atr", "2.4"),
       ("risk_ratio", "0.02"), ("risk_ratio", "0.03"), ("max_weight", "0.392"), ("max_weight", "0.588")]


def windows(p: dict, slip: str = "0.0005") -> list[dict]:
    out = []
    for s, e in WIN:
        r = replay(SYMS, p, s, e, Decimal(slip), skip_hours=SKIP)
        out.append({"year": s.year, "n": len(r["pnls"]), "pnl": float(sum(r["pnls"], Decimal(0))), "ret": float(r["final"] / 10000 - 1),
                    "mdd": float(r["mdd"])})
    return out


def agg(ws: list[dict], yrs: range = range(2019, 2026)) -> tuple[int, float]:
    sel = [w for w in ws if w["year"] in yrs]
    n = sum(w["n"] for w in sel)
    return n, sum(w["pnl"] for w in sel) / n if n else float("nan")


p0 = base_params(2)
T = {"base": windows(p0), "slip0.2%": windows(p0, "0.002")}
for k, v in VAR:
    T[f"{k}={v}"] = windows(dict(p0, **{k: v}))
print("P. crypto-trend v1(strategy.py, 2종목 한 계좌) 사전 판정표 — 1시간 재생, 7창 · 판정 아님(과대 추정)")
for name, ws in T.items():
    n, ev = agg(ws)
    print(f"  {name:18s} 거래 {n:3d}(6창 {agg(ws, range(2020, 2026))[0]:3d}) · 거래당 {ev:+8.1f} USDT · 손실 창 {sum(1 for w in ws if w['ret'] < 0)}/7")
print("  창별(base): " + " · ".join(f"{w['year']} {w['ret']:+.0%}·MDD {w['mdd']:.0%}({w['n']})" for w in T["base"]))
n7, n6 = agg(T["base"])[0], agg(T["base"], range(2020, 2026))[0]
c3 = agg(T["slip0.2%"])[1] > 0
c4 = all(agg(T[k])[1] > 0 for k in T if "=" in k)
print(f"  C-2 7창 {n7}·6창 {n6} · C-3 {'충족' if c3 else '미충족'} · C-4 {'충족' if c4 else '미충족'}")
print(f"  사전 기준: {'crypto-trend v1 인계 후보(장중 엔진 공식 재현 필요)' if c3 and c4 else '보류'}")
(LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-crypto-trend-preverdict{'-ops23' if SKIP else ''}.json").write_text(
    json.dumps({"table": T, "C2": [n7, n6], "C3": c3, "C4": c4}, ensure_ascii=False, indent=1), encoding="utf-8")

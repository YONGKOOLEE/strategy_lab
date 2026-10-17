"""L. 2종목(BTC·ETH) 1시간판 A-h 사전 판정표 — 7창 합산. 판정 아님. 사전 등록: research/2026-10-18-overnight-design.md L.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import Data  # noqa: E402
from btc_v2_preverdict import BASE, VARIANTS, windows  # noqa: E402


def combo(Ds: dict, p: dict, slip: float) -> list[dict]:
    per = [windows(D, True, p, slip) for D in Ds.values()]
    out = []
    for ws in zip(*per):
        out.append({"year": ws[0]["year"], "trades": sum(w["trades"] for w in ws), "pnl": sum(w["pnl"] for w in ws) / 2,
                    "ret": sum(w["ret"] for w in ws) / 2})
    return out


def agg(ws: list[dict], yrs: range = range(2019, 2026)) -> tuple[int, float]:
    sel = [w for w in ws if w["year"] in yrs]
    n = sum(w["trades"] for w in sel)
    return n, sum(w["pnl"] for w in sel) / n if n else float("nan")


def main() -> int:
    Ds = {s: Data(s) for s in ("BTCUSDT", "ETHUSDT")}
    p0 = dict(BASE, gate=True)
    T = {"base": combo(Ds, p0, 0.0005), "slip0.2%": combo(Ds, p0, 0.002)}
    for k, v in VARIANTS:
        T[f"{k}={v}"] = combo(Ds, dict(p0, **{k: v}), 0.0005)
    print("L. 2종목 1시간판(A-h) 반반 사전 판정표 — 7창 2019~2025 · 판정 아님(과대 추정)")
    for name, ws in T.items():
        n, ev = agg(ws)
        print(f"  {name:14s} 거래 {n:3d}(6창 {agg(ws, range(2020, 2026))[0]:3d}) · 거래당 {ev:+8.1f} USDT · 손실 창 {sum(1 for w in ws if w['ret'] < 0)}/7")
    print("  창별(base): " + " · ".join(f"{w['year']} {w['ret']:+.0%}({w['trades']})" for w in T["base"]))
    n7, n6 = agg(T["base"])[0], agg(T["base"], range(2020, 2026))[0]
    c3 = agg(T["slip0.2%"])[1] > 0
    c4 = all(agg(T[k])[1] > 0 for k in T if "=" in k)
    print(f"  C-2 7창 {n7}·6창 {n6} ({'충족' if n7 >= 100 else '미달'}/{'충족' if n6 >= 100 else '미달'}) · C-3 {'충족' if c3 else '미충족'} · C-4 {'충족' if c4 else '미충족'}")
    print(f"  사전 기준: {'2종목 1시간판 v2 후보 유지' if c3 and c4 else '폐기'}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-two-coin-preverdict.json"
    f.write_text(json.dumps({"table": T, "C2": [n7, n6], "C3": c3, "C4": c4}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""(a) v1 1시간 판정판 사전 판정표 — 1시간 모형(research/btc_intraday_study.py). 판정 아님.
사전 등록: research/2026-10-18-intraday-design.md "추가 등록 — (a) v1 1시간 판정판 사전 판정표"(2026-10-18 01:05).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import FEE, Data, buy_hold, simulate, v1  # noqa: E402

WINDOWS = [(date(y, 1, 1), date(y, 12, 31)) for y in range(2019, 2026)]
BASE = dict(entry_n=25, exit_n=50, stop_atr=2.0, risk=0.05, maxw=0.98)
VARIANTS = [("entry_n", 20), ("entry_n", 30), ("exit_n", 40), ("exit_n", 60), ("stop_atr", 1.6), ("stop_atr", 2.4),
            ("risk", 0.04), ("risk", 0.06), ("maxw", 0.784), ("maxw", 1.0)]


def windows(D: Data, hourly: bool, p: dict, slip: float) -> list[dict]:
    out = []
    for s, e in WINDOWS:
        r = simulate(D, v1(hourly, **p), s, e, slip)
        pnl = [q * (x * (1 - FEE) - en * (1 + FEE)) for _, _, en, x, q, _ in r["trade_list"]]
        out.append({"year": s.year, "trades": len(pnl), "pnl": sum(pnl), "ret": r["ret"], "mdd": r["mdd"],
                    "entries": [t[0] for t in r["trade_list"]]})
    return out


def agg(ws: list[dict], years: range = range(2019, 2026)) -> tuple[int, float]:
    sel = [w for w in ws if w["year"] in years]
    n = sum(w["trades"] for w in sel)
    return n, (sum(w["pnl"] for w in sel) / n if n else float("nan"))


def main() -> int:
    D = Data()
    sets = {"base": (BASE, 0.0005), "slip0.2%": (BASE, 0.002), "slip0.1%": (BASE, 0.001)}
    for k, v in VARIANTS:
        sets[f"{k}={v}"] = (dict(BASE, **{k: v}), 0.0005)
    T = {name: windows(D, True, p, sl) for name, (p, sl) in sets.items()}
    daily = windows(D, False, BASE, 0.0005)
    print("v1 1시간 판정판 사전 판정표 — 1시간 모형, 7창 2019~2025, 판정 아님(과대 추정)")
    for name, ws in T.items():
        n, ev = agg(ws)
        n6, _ = agg(ws, range(2020, 2026))
        print(f"  {name:16s} 7창 거래 {n:3d}(6창 {n6:3d}) · 거래당 {ev:+9.1f} USDT · 손실 창 {sum(1 for w in ws if w['ret'] < 0)}/7")
    n, ev = agg(daily)
    print(f"  (비교) v1 일봉   7창 거래 {n:3d}(6창 {agg(daily, range(2020, 2026))[0]:3d}) · 거래당 {ev:+9.1f} USDT · 손실 창 {sum(1 for w in daily if w['ret'] < 0)}/7")
    print("\n창별: 연도 · 1시간판 수익·MDD·거래 | 일봉 v1 수익·MDD·거래 | 그냥 보유 수익·MDD")
    for w, d in zip(T["base"], daily):
        bh = buy_hold(D, date(w["year"], 1, 1), date(w["year"], 12, 31))
        print(f"  {w['year']} {w['ret']:+7.1%} {w['mdd']:5.1%} {w['trades']:2d} | {d['ret']:+7.1%} {d['mdd']:5.1%} {d['trades']:2d} | {bh['ret']:+7.1%} {bh['mdd']:5.1%}")
    n7, _ = agg(T["base"])
    n6, _ = agg(T["base"], range(2020, 2026))
    c3 = agg(T["slip0.2%"])[1] > 0
    var = [k for k in T if "=" in k]
    same = [k for k in var if [w["entries"] for w in T[k]] == [w["entries"] for w in T["base"]] and
            [round(w["pnl"], 6) for w in T[k]] == [round(w["pnl"], 6) for w in T["base"]]]
    c4 = all(agg(T[k])[1] > 0 for k in var)
    print(f"\nC-2 7창 {n7}·6창 {n6} (≥ 100? {'충족' if n7 >= 100 else '미달'}/{'충족' if n6 >= 100 else '미달'}) · C-3 {'충족' if c3 else '미충족'} · "
          f"C-4 {'충족' if c4 else '미충족'} (결과 동일: {same or '없음'}) · C-7 과대 추정")
    verdict = "btc-trend v2(1시간 판정) 후보" if c3 and c4 else "장중판 폐기(일봉 v1 유지)"
    print(f"사전 기준: {verdict}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-v2-preverdict.json"
    for ws in list(T.values()) + [daily]:
        for w in ws:
            w.pop("entries")
    f.write_text(json.dumps({"table": T, "daily_v1": daily, "C2": [n7, n6], "C3": c3, "C4": c4, "same": same, "verdict": verdict},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {f.relative_to(LAB)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

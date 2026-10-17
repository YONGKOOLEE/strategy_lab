"""H. BTC/ETH 듀얼 모멘텀(매주 월요일, L일 수익률 큰 쪽이 > 0이면 98% 보유). 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md H.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import cryptosim as cs  # noqa: E402

FEE, SLIP, TICK, STEP = 0.001, 0.0005, 0.01, 0.00001
PER = {"학습": (date(2017, 9, 1), date(2021, 12, 31)), "확인": (date(2022, 1, 1), date(2025, 12, 31)), "전체": (date(2017, 9, 1), date(2025, 12, 31))}


def simulate(data: dict, start: date, end: date, L: int) -> dict:
    syms = list(data)
    dates = sorted(set.intersection(*[{r[0] for r in data[s]} for s in syms]))
    row = {s: {r[0]: r for r in data[s]} for s in syms}
    idx = {s: {r[0]: k for k, r in enumerate(data[s])} for s in syms}
    cl = {s: [r[4] for r in data[s]] for s in syms}
    cash, held, qty, pend, curve, switches = 10000.0, None, 0.0, "none", [], 0
    for d in dates:
        if not (start <= d <= end):
            continue
        if pend != "none":
            if held is not None and qty > 0:
                px = math.floor(row[held][d][1] * (1 - SLIP) / TICK) * TICK
                cash += qty * px * (1 - FEE)
                qty, held = 0.0, None
            if pend is not None:
                px = math.ceil(row[pend][d][1] * (1 + SLIP) / TICK) * TICK
                q = math.floor(cash * 0.98 / (px * (1 + FEE)) / STEP) * STEP
                cash -= q * px * (1 + FEE)
                qty, held = q, pend
            switches += 1
            pend = "none"
        if d.weekday() == 0:
            mom = {}
            for s in syms:
                k = idx[s][d]
                if k >= L:
                    mom[s] = cl[s][k] / cl[s][k - L] - 1
            if len(mom) == len(syms):
                best = max(mom, key=mom.get)
                want = best if mom[best] > 0 else None
                if want != held:
                    pend = want
        curve.append((d, cash + (qty * cl[held][idx[held][d]] if held else 0.0)))
    peak, mdd = 0.0, 0.0
    for _, v in curve:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    ret = curve[-1][1] / 10000 - 1
    cagr = (1 + ret) ** (365.25 / ((end - start).days + 1)) - 1
    return {"ret": ret, "mdd": mdd, "ratio": cagr / mdd if mdd else float("inf"), "switches": switches, "curve": curve}


def main() -> int:
    data = {s: cs.load_csv(LAB / "data" / "crypto" / f"{s}-1d.csv") for s in ("BTCUSDT", "ETHUSDT")}
    b4 = json.loads((LAB / "results" / "cryptosim" / "20261018-eth-daily.json").read_text(encoding="utf-8"))["combo"]
    out = {}
    print("H. 듀얼 모멘텀(매주 월요일) — 수익·MDD·비율·교체 | B4 독립 50:50 v1")
    for L in (60, 90, 180):
        out[L] = {pn: simulate(data, s, e, L) for pn, (s, e) in PER.items()}
        print(f"  L{L}: " + " | ".join(f"{pn} {out[L][pn]['ret']:+7.0%} {out[L][pn]['mdd']:5.1%} {out[L][pn]['ratio']:.2f} ({out[L][pn]['switches']})" for pn in PER))
    print("  B4:  " + " | ".join(f"{pn} {b4[pn]['ret']:+7.0%} {b4[pn]['mdd']:5.1%} {b4[pn]['ratio']:.2f}" for pn in PER))
    pick = max(out, key=lambda L: out[L]["학습"]["ratio"])
    ok = all(out[pick][p]["ratio"] > b4[p]["ratio"] for p in ("학습", "확인"))
    print(f"  학습 선택 L{pick} → 사전 기준: {'듀얼 모멘텀 후보(가설)' if ok else '폐기'}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-dual-momentum.json"
    f.write_text(json.dumps({str(L): {p: {k: v for k, v in x.items() if k != 'curve'} for p, x in r.items()} for L, r in out.items()} | {"pick": pick, "ok": ok},
                            ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

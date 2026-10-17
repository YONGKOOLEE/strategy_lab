"""G. BTC+ETH 공유 계좌 v1 — 여러 종목 일봉 시뮬레이터(cryptosim v1 경로와 같은 체결 규칙). 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md G (2026-10-18 01:18).
체결: 판정 = 일봉 종가, 다음 날 시가 × (1 ± 슬리피지)를 호가 0.01로 올림/내림, 수수료 0.1%, 수량 0.00001 내림·최소 5 USDT.
크기: min(자산 × 위험 ÷ (손절 거리 비율), 자산 × 종목 상한) ÷ 가격, 남은 현금 한도. 자산 = 현금 + 보유 × 그날 시가. 매도 먼저, 매수는 종목 순서대로.
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


def simulate(data: dict, start: date, end: date, cap: float, risk: float = 0.05, entry_n: int = 25, exit_n: int = 50,
             stop_atr: float = 2.0) -> dict:
    syms = list(data)
    dates = sorted(set.intersection(*[{r[0] for r in data[s]} for s in syms]))
    rows = {s: {r[0]: r for r in data[s]} for s in syms}
    idx = {s: {r[0]: k for k, r in enumerate(data[s])} for s in syms}
    closes = {s: [r[4] for r in data[s]] for s in syms}
    atr = {s: cs.atr_series(data[s]) for s in syms}
    cash = 10000.0
    pos = {s: {"qty": 0.0, "stop": 0.0, "pend": None} for s in syms}
    curve, trades = [], 0
    for d in dates:
        if not (start <= d <= end):
            continue
        eq_open = cash + sum(pos[s]["qty"] * rows[s][d][1] for s in syms)
        for s in syms:                                   # 매도 먼저
            p = pos[s]
            if p["pend"] == "sell" and p["qty"] > 0:
                px = math.floor(rows[s][d][1] * (1 - SLIP) / TICK) * TICK
                cash += p["qty"] * px * (1 - FEE)
                p["qty"], p["pend"] = 0.0, None
                trades += 1
        for s in syms:                                   # 매수(종목 순서)
            p = pos[s]
            if isinstance(p["pend"], tuple) and p["qty"] == 0:
                px = math.ceil(rows[s][d][1] * (1 + SLIP) / TICK) * TICK
                sl = px - stop_atr * p["pend"][1]
                dist = (px - sl) / px
                w = min(cap, risk / dist) if dist > 0 else 0.0
                q = math.floor(min(eq_open * w, cash) / (px * (1 + FEE)) / STEP) * STEP
                if q * px >= 5 and dist > 0 and sl > 0:
                    cash -= q * px * (1 + FEE)
                    p["qty"], p["stop"] = q, sl
            if isinstance(p["pend"], tuple):
                p["pend"] = None
        for s in syms:                                   # 종가 판정
            p, k, c = pos[s], idx[s][d], closes[s]
            cl = c[k]
            if p["qty"] > 0:
                if cl < p["stop"]:
                    p["pend"] = "sell"
                elif k + 1 >= exit_n and cl < sum(c[k - exit_n + 1:k + 1]) / exit_n:
                    p["pend"] = "sell"
            elif k >= entry_n and cl > max(c[k - entry_n:k]) and atr[s][k] is not None:
                p["pend"] = ("buy", atr[s][k])
        curve.append((d, cash + sum(pos[s]["qty"] * closes[s][idx[s][d]] for s in syms)))
    peak, mdd = 0.0, 0.0
    for _, v in curve:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    ret = curve[-1][1] / 10000 - 1
    cagr = (1 + ret) ** (365.25 / ((end - start).days + 1)) - 1
    return {"ret": ret, "mdd": mdd, "ratio": cagr / mdd if mdd else float("inf"), "trades": trades}


def main() -> int:
    data = {s: cs.load_csv(LAB / "data" / "crypto" / f"{s}-1d.csv") for s in ("BTCUSDT", "ETHUSDT")}
    chk = simulate({"BTCUSDT": data["BTCUSDT"]}, *PER["전체"], cap=0.98)
    print(f"도구 확인(BTC만, 상한 98%): {chk['ret']:+.1%}·거래 {chk['trades']} (cryptosim v1 +6,081%·41건과 같아야 함)")
    res = json.loads((LAB / "results" / "cryptosim" / "20261018-eth-daily.json").read_text(encoding="utf-8"))
    out = {}
    for name, cap, rk in (("G-98", 0.98, 0.05), ("G-49", 0.49, 0.05), ("G-ops", 0.49, 0.025)):   # G-ops: G2 추가 등록(정보)
        out[name] = {pn: simulate(data, s, e, cap, risk=rk) for pn, (s, e) in PER.items()}
    print("G. 공유 계좌(BTC+ETH) vs 독립 50:50(B4) vs BTC 단독 — 수익·MDD·비율·청산 거래")
    for pn in PER:
        b4, bt = res["combo"][pn], res["v1"]["BTCUSDT"][pn]
        print(f"  {pn}: " + " | ".join(f"{n} {out[n][pn]['ret']:+7.0%} {out[n][pn]['mdd']:5.1%} {out[n][pn]['ratio']:.2f} ({out[n][pn]['trades']})" for n in out)
              + f" | 독립 50:50 {b4['ret']:+7.0%} {b4['mdd']:5.1%} {b4['ratio']:.2f} | BTC 단독 {bt['ratio']:.2f}")
    ok = any(all(out[n][p]["ratio"] > res["combo"][p]["ratio"] for p in ("학습", "확인")) for n in ("G-98", "G-49"))
    print(f"  사전 기준: {'공유 계좌 우위(가설)' if ok else '독립 계좌로 충분'}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-shared-account.json"
    f.write_text(json.dumps({"check": chk, "G": out, "ok": ok}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

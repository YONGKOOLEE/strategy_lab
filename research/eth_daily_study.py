"""B. ETH 일봉 부분 — v1(cryptosim, UTC00) BTC·ETH 비교(B3), BTC+ETH 50:50 묶기(B4). 판정 아님.
사전 등록: research/2026-10-18-btc-preverdict-design.md "추가 등록 — 이더리움"(00:45), research/2026-10-18-overnight-design.md B(01:12).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import cryptosim as cs  # noqa: E402

V1 = dict(entry_rule="breakout", entry_n=25, exit_mode="sma", exit_n=50, stop_mode="atr", stop_atr=2.0, stop_when="close",
          risk_ratio=0.05, max_weight=0.98)
PER = {"학습": (date(2017, 9, 1), date(2021, 12, 31)), "확인": (date(2022, 1, 1), date(2025, 12, 31)), "전체": (date(2017, 9, 1), date(2025, 12, 31))}


def metrics(curve: list, cash: float, s: date, e: date) -> tuple[float, float, float]:
    peak, mdd = 0.0, 0.0
    for _, v in curve:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    ret = curve[-1][1] / cash - 1
    cagr = (1 + ret) ** (365.25 / ((e - s).days + 1)) - 1
    return ret, mdd, cagr / mdd if mdd else float("inf")


def bh_ratio(r: dict, s: date, e: date) -> float:
    cagr = (1 + r["buy_hold_ret"]) ** (365.25 / ((e - s).days + 1)) - 1
    return cagr / r["buy_hold_mdd"]


def main() -> int:
    rows = {s: cs.load_csv(LAB / "data" / "crypto" / f"{s}-1d.csv") for s in ("BTCUSDT", "ETHUSDT")}
    out: dict = {}
    print("v1(cryptosim UTC00) — 수익·MDD·비율·거래 | 그냥 보유 · 판정 아님(과대 추정)")
    for sym, rw in rows.items():
        out[sym] = {}
        for pn, (s, e) in PER.items():
            r = cs.simulate(rw, dict(cs.DEFAULTS, **V1), s, e)
            ret, mdd, ratio = metrics(r["eq_curve"], 10000.0, s, e)
            out[sym][pn] = {"ret": ret, "mdd": mdd, "ratio": ratio, "trades": r["trades"], "win": r["win_rate"],
                            "bh_ret": r["buy_hold_ret"], "bh_mdd": r["buy_hold_mdd"], "bh_ratio": bh_ratio(r, s, e), "year": r["year_ret"]}
            x = out[sym][pn]
            print(f"  {sym} {pn}: {ret:+8.0%} MDD {mdd:5.1%} 비율 {ratio:5.2f} 거래 {r['trades']:2d} 승률 {r['win_rate']:.0%} | 보유 {x['bh_ret']:+7.0%} MDD {x['bh_mdd']:5.1%} 비율 {x['bh_ratio']:5.2f}")
    print("  ETH 연도별(v1 / 보유 근사 없음): " + " ".join(f"{y}:{v:+.0%}" for y, v in out["ETHUSDT"]["전체"]["year"].items()))
    eth = out["ETHUSDT"]
    beat = [eth[p]["ratio"] > eth[p]["bh_ratio"] for p in ("학습", "확인")]
    print(f"\n(a) UTC00 기준 그냥 보유 대비 비율 우위: 학습 {beat[0]} · 확인 {beat[1]}")
    print("\nB4 BTC+ETH 50:50(각 v1 독립 계좌)")
    combo = {}
    for pn, (s, e) in PER.items():
        ca = cs.simulate(rows["BTCUSDT"], dict(cs.DEFAULTS, **V1, cash=5000.0), s, e)["eq_curve"]
        cb = cs.simulate(rows["ETHUSDT"], dict(cs.DEFAULTS, **V1, cash=5000.0), s, e)["eq_curve"]
        db = dict(cb)
        cur = [(d, v + db[d]) for d, v in ca if d in db]
        ret, mdd, ratio = metrics(cur, 10000.0, s, e)
        combo[pn] = {"ret": ret, "mdd": mdd, "ratio": ratio}
        b = out["BTCUSDT"][pn]
        print(f"  {pn}: 묶기 {ret:+8.0%} MDD {mdd:5.1%} 비율 {ratio:.2f} | BTC 단독 {b['ret']:+8.0%} MDD {b['mdd']:5.1%} 비율 {b['ratio']:.2f}")
    ok = all(combo[p]["ratio"] > out["BTCUSDT"][p]["ratio"] and combo[p]["mdd"] < out["BTCUSDT"][p]["mdd"] for p in ("학습", "확인"))
    print(f"  사전 기준: {'2종목 확장 효과(가설)' if ok else '효과 없음'}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-eth-daily.json"
    f.write_text(json.dumps({"v1": out, "combo": combo, "combo_ok": ok, "utc00_beat": beat}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

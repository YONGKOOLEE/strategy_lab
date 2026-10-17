"""C 기간 앙상블 · D 워크포워드 재선택 튜닝 · E 거래 재표본 — BTC·ETH, cryptosim UTC00. 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md C·D·E (2026-10-18 01:16).
  python research/crypto_overnight_cde.py   → 표준출력 + results/cryptosim/<날짜>-cde.json
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import cryptosim as cs  # noqa: E402

V1 = dict(entry_rule="breakout", entry_n=25, exit_mode="sma", exit_n=50, stop_mode="atr", stop_atr=2.0, stop_when="close",
          risk_ratio=0.05, max_weight=0.98)
PER = {"학습": (date(2017, 9, 1), date(2021, 12, 31)), "확인": (date(2022, 1, 1), date(2025, 12, 31))}
SYMS = ("BTCUSDT", "ETHUSDT")


def metrics(curve: list, cash: float, s: date, e: date) -> dict:
    peak, mdd = 0.0, 0.0
    for _, v in curve:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    ret = curve[-1][1] / cash - 1
    cagr = (1 + ret) ** (365.25 / ((e - s).days + 1)) - 1
    return {"ret": ret, "mdd": mdd, "ratio": cagr / mdd if mdd else float("inf")}


def run(rows: list, s: date, e: date, cash: float = 10000.0, **kw: object) -> dict:
    return cs.simulate(rows, dict(cs.DEFAULTS, **dict(V1, **kw), cash=cash), s, e)


def part_c(rows: dict) -> dict:
    out = {}
    print("C. 기간 앙상블(9 하위 계좌: 돌파 15·25·40 × 청산 40·50·60) vs v1(25·50)")
    for sym in SYMS:
        out[sym] = {}
        for pn, (s, e) in PER.items():
            v = run(rows[sym], s, e)
            mv = metrics(v["eq_curve"], 10000.0, s, e) | {"trades": v["trades"]}
            tot, trades = None, 0
            for en in (15, 25, 40):
                for ex in (40, 50, 60):
                    r = run(rows[sym], s, e, cash=10000.0 / 9, entry_n=en, exit_n=ex)
                    trades += r["trades"]
                    tot = r["eq_curve"] if tot is None else [(d, a + b) for (d, a), (_, b) in zip(tot, r["eq_curve"])]
            me = metrics(tot, 10000.0, s, e) | {"trades": trades}
            out[sym][pn] = {"v1": mv, "ens": me}
            print(f"  {sym} {pn}: 앙상블 {me['ret']:+7.0%} MDD {me['mdd']:5.1%} 비율 {me['ratio']:.2f} 거래 {trades} | v1 {mv['ret']:+7.0%} MDD {mv['mdd']:5.1%} 비율 {mv['ratio']:.2f} 거래 {mv['trades']}")
    ok = all(out[s][p]["ens"]["ratio"] >= 0.95 * out[s][p]["v1"]["ratio"] and out[s][p]["ens"]["mdd"] <= out[s][p]["v1"]["mdd"]
             for s in SYMS for p in PER)
    print(f"  사전 기준: {'앙상블 v2 후보(가설)' if ok else 'v1 단일 유지'}")
    out["ok"] = ok
    return out


def part_d(rows: dict) -> dict:
    grid = [(en, ex) for en in (10, 15, 20, 25, 30, 40, 55) for ex in (20, 30, 40, 50, 60, 80)]
    out = {}
    print("\nD. 워크포워드 재선택(직전 3년 비율 최고 → 다음 해) vs 고정 v1(25·50)")
    for sym in SYMS:
        rows_ = rows[sym]
        yrs = []
        for y in range(2020, 2026):
            ts, te = (date(2017, 9, 1) if y == 2020 else date(y - 3, 1, 1)), date(y - 1, 12, 31)
            best = max(grid, key=lambda g: metrics(run(rows_, ts, te, entry_n=g[0], exit_n=g[1])["eq_curve"], 10000.0, ts, te)["ratio"])
            s, e = date(y, 1, 1), date(y, 12, 31)
            wf = run(rows_, s, e, entry_n=best[0], exit_n=best[1])["ret"]
            fx = run(rows_, s, e)["ret"]
            yrs.append({"year": y, "pick": best, "wf": wf, "fixed": fx})
        cum_wf = cum_fx = 1.0
        for x in yrs:
            cum_wf *= 1 + x["wf"]
            cum_fx *= 1 + x["fixed"]
        wins = sum(1 for x in yrs if x["wf"] > x["fixed"])
        out[sym] = {"years": yrs, "cum_wf": cum_wf - 1, "cum_fixed": cum_fx - 1, "wins": wins}
        print(f"  {sym}: " + " · ".join(f"{x['year']} {x['pick']} {x['wf']:+.0%}/{x['fixed']:+.0%}" for x in yrs))
        print(f"    재선택 우위 {wins}/6년 · 6년 누적 재선택 {cum_wf - 1:+.0%} vs 고정 {cum_fx - 1:+.0%}")
    ok = all(out[s]["wins"] >= 4 and out[s]["cum_wf"] > out[s]["cum_fixed"] for s in SYMS)
    print(f"  사전 기준: {'재선택 튜닝 가치 있음(가설)' if ok else '고정 파라미터 유지 — 추가 튜닝은 과최적화 위험만'}")
    out["ok"] = ok
    return out


def part_e(rows: dict) -> dict:
    out = {}
    print("\nE. 거래 재표본 10,000회(같은 거래 수, 복원 추출) — 최종 배수·MDD 분위수(5/25/50/75/95%)")
    rng = random.Random(20261018)
    s, e = date(2017, 9, 1), date(2025, 12, 31)
    for sym in SYMS:
        r = run(rows[sym], s, e)
        eq = dict(r["eq_curve"])
        days = [d for d, _ in r["eq_curve"]]
        rets = []
        for en, _ex, epx, xpx, q, _ in r["trade_list"]:
            k = days.index(en)
            base = eq[days[k - 1]] if k > 0 else 10000.0
            rets.append(q * (xpx * (1 - 0.001) - epx * (1 + 0.001)) / base)
        out[sym] = {}
        for lab, pool in (("전체", rets), ("상위 3건 제외", sorted(rets)[:-3])):
            finals, mdds = [], []
            for _ in range(10000):
                v, peak, mdd = 1.0, 1.0, 0.0
                for _ in range(len(pool)):
                    v *= 1 + rng.choice(pool)
                    peak = max(peak, v)
                    mdd = max(mdd, 1 - v / peak)
                finals.append(v)
                mdds.append(mdd)
            finals.sort()
            mdds.sort()
            q = lambda xs, p: xs[int(p * (len(xs) - 1))]  # noqa: E731
            out[sym][lab] = {"n": len(pool), "final": [q(finals, p) for p in (0.05, 0.25, 0.5, 0.75, 0.95)],
                             "mdd": [q(mdds, p) for p in (0.05, 0.25, 0.5, 0.75, 0.95)], "p_loss": sum(1 for x in finals if x < 1) / len(finals)}
            x = out[sym][lab]
            print(f"  {sym} {lab}({x['n']}건): 최종 배수 " + "/".join(f"{v:.1f}" for v in x["final"]) +
                  " · MDD " + "/".join(f"{v:.0%}" for v in x["mdd"]) + f" · 원금 손실 확률 {x['p_loss']:.1%}")
    return out


def main() -> int:
    rows = {s: cs.load_csv(LAB / "data" / "crypto" / f"{s}-1d.csv") for s in SYMS}
    res = {"C": part_c(rows), "D": part_d(rows), "E": part_e(rows)}
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-cde.json"
    f.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n저장: {f.relative_to(LAB)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""K. BTC·ETH 1시간판(A-h: 1시간 판정·게이트) 반반 vs 일봉 v1 반반 — 1시간 모형. 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md K (2026-10-18 01:26).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import CONF, FULL, TRAIN, Data  # noqa: E402
import btc_intraday_study as bis  # noqa: E402


def half_curve(D: Data, hourly: bool, gate: bool, s: date, e: date) -> dict:
    r = bis.simulate(D, bis.v1(hourly, gate=gate), s, e, 0.0005)
    return {d: v / 2 for d, v in r["daily"].items()}, r["trades"]          # 10,000 시작 곡선의 절반 = 5,000 하위 계좌


def metrics(curve: dict, s: date, e: date) -> dict:
    peak, mdd = 0.0, 0.0
    for d in sorted(curve):
        v = curve[d]
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    ret = curve[max(curve)] / 10000 - 1
    cagr = (1 + ret) ** (365.25 / ((e - s).days + 1)) - 1
    return {"ret": ret, "mdd": mdd, "ratio": cagr / mdd if mdd else float("inf")}


def main() -> int:
    Ds = {s: Data(s) for s in ("BTCUSDT", "ETHUSDT")}
    out = {}
    print("K. 2종목 반반(일별 자산 합산) — 수익·MDD·비율·거래 · 판정 아님(과대 추정)")
    for name, (hourly, gate) in (("일봉 v1 반반", (False, False)), ("1시간판 A-h 반반", (True, True))):
        out[name] = {}
        for pn, (s, e) in (("학습", TRAIN), ("확인", CONF), ("전체", FULL)):
            parts = [half_curve(Ds[x], hourly, gate, s, e) for x in Ds]
            days = sorted(set(parts[0][0]) & set(parts[1][0]))
            cur = {d: parts[0][0][d] + parts[1][0][d] for d in days}
            m = metrics(cur, s, e) | {"trades": parts[0][1] + parts[1][1]}
            out[name][pn] = m
        print(f"  {name:14s} " + " | ".join(f"{pn} {m['ret']:+7.0%} {m['mdd']:5.1%} {m['ratio']:.2f} ({m['trades']})" for pn, m in out[name].items()))
    a, b = out["1시간판 A-h 반반"], out["일봉 v1 반반"]
    ok = all(a[p]["ratio"] > b[p]["ratio"] for p in ("학습", "확인"))
    print(f"  사전 기준: {'2종목 1시간판 후보(가설)' if ok else '일봉 반반 유지'}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-two-coin-hourly.json"
    f.write_text(json.dumps({"rows": out, "ok": ok}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""AA. 단타판 — v1 구조를 봉 단위(1시간·15분)로. 판정 아님. 사전 등록: research/2026-10-18-overnight-design.md AA (02:41)."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
sys.path.insert(0, str(LAB / "research"))
import cryptosim as cs  # noqa: E402
from btc_monitor_study import load_hours  # noqa: E402

P = dict(entry_rule="breakout", entry_n=25, regime_n=50, exit_mode="sma", exit_n=50, stop_mode="atr", stop_atr=2.0, stop_when="close",
         risk_ratio=0.05, max_weight=0.98)
PER = {"학습": (datetime(2017, 9, 1), datetime(2021, 12, 31, 23, 59)), "후기": (datetime(2022, 1, 1), datetime(2025, 12, 31, 23, 59))}


def ratio(ret: float, mdd: float, s: datetime, e: datetime) -> float:
    cagr = (1 + ret) ** (365.25 / max((e - s).days, 1)) - 1 if ret > -1 else -1.0
    return cagr / mdd if mdd > 0 else float("inf")


out, ok_any = {}, False
for sym in ("BTCUSDT", "ETHUSDT"):
    for tf in ("1h", "15m"):
        rows = load_hours(LAB / "data" / "crypto" / f"{sym}-{tf}.csv")
        res = {}
        for pn, (s, e) in PER.items():
            r = cs.simulate(rows, dict(cs.DEFAULTS, **P), s, e)
            r2 = cs.simulate(rows, dict(cs.DEFAULTS, **P, fee=0.0005), s, e)
            hold = [(datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 3600 for a, b, *_ in r["trade_list"]]
            res[pn] = {"ret": r["ret"], "mdd": r["mdd"], "ratio": ratio(r["ret"], r["mdd"], s, e), "trades": r["trades"], "win": r["win_rate"],
                       "ev": r["avg_ret"], "ev_fee005": r2["avg_ret"], "ret_fee005": r2["ret"], "hold_med_h": sorted(hold)[len(hold) // 2] if hold else 0,
                       "bh_ratio": ratio(r["buy_hold_ret"], r["buy_hold_mdd"], s, e)}
        out[f"{sym} {tf}"] = res
        ok = all(res[p]["ev"] > 0 and res[p]["ratio"] > res[p]["bh_ratio"] for p in PER)
        ok_any |= ok
        print(f"{sym} {tf}: " + " | ".join(f"{p} {x['ret']:+.0%}·MDD {x['mdd']:.0%}·비율 {x['ratio']:.2f}(보유 {x['bh_ratio']:.2f})·{x['trades']}건·승률 {x['win']:.0%}·거래당 {x['ev']:+.2%}(수수료 0.05% {x['ev_fee005']:+.2%})·보유 중앙 {x['hold_med_h']:.0f}h"
                                       for p, x in res.items()) + f" → {'통과' if ok else '미달'}")
print(f"사전 기준: {'단타판 후보(가설)' if ok_any else '단타판 폐기 — 비용이 우위를 넘음'}")
(LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-scalp.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

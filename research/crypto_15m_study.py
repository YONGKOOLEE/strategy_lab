"""M. A-h(1시간 판정·게이트) 60분 vs 15분 판정 — BTC·ETH. 판정 아님. 사전 등록: research/2026-10-18-overnight-design.md M.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import CONF, FULL, TRAIN, Data, simulate, v1  # noqa: E402

res = {}
for sym in ("BTCUSDT", "ETHUSDT"):
    for tf in ("1h", "15m"):
        D = Data(sym, tf)
        row = {}
        for pn, (s, e) in (("학습", TRAIN), ("확인", CONF), ("전체", FULL)):
            r = simulate(D, v1(True, gate=True), s, e, 0.0005)
            short = sum(1 for a, b, *_ in r["trade_list"] if (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() <= 3 * 3600)
            row[pn] = (r["ratio"], r["ret"], r["mdd"], r["trades"], short)
        res[(sym, tf)] = row
        print(f"{sym} {tf:3s}: " + " | ".join(f"{pn} {x[0]:.2f} ({x[1]:+.0%}·MDD {x[2]:.1%}·{x[3]}건·짧은 {x[4]})" for pn, x in row.items()))
ok = all(res[(s, "15m")][p][0] >= res[(s, "1h")][p][0] for s in ("BTCUSDT", "ETHUSDT") for p in ("학습", "확인"))
print(f"사전 기준: {'15분 판정 후보' if ok else '60분 유지'}")

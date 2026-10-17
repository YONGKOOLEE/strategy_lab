"""N. A-h 손절: 1시간 종가 판정 vs 장중 감시(저가 닿으면 손절가) — BTC·ETH. 사전 등록: research/2026-10-18-overnight-design.md N."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import CONF, FULL, TRAIN, Data, simulate, v1  # noqa: E402

res = {}
for sym in ("BTCUSDT", "ETHUSDT"):
    D = Data(sym)
    for lab, ist in (("종가 손절", False), ("장중 손절", True)):
        row = {}
        for pn, (s, e) in (("학습", TRAIN), ("확인", CONF), ("전체", FULL)):
            r = simulate(D, v1(True, gate=True, istop=ist), s, e, 0.0005)
            row[pn] = (r["ratio"], r["ret"], r["mdd"], r["trades"], Counter(t[5] for t in r["trade_list"]))
        res[(sym, lab)] = row
        print(f"{sym} {lab}: " + " | ".join(f"{pn} {x[0]:.2f} ({x[1]:+.0%}·MDD {x[2]:.1%}·{x[3]}건 {dict(x[4])})" for pn, x in row.items()))
d = {(s, p): res[(s, "장중 손절")][p][0] / res[(s, "종가 손절")][p][0] - 1 for s in ("BTCUSDT", "ETHUSDT") for p in ("학습", "확인")}
print("비율 변화(장중/종가 − 1): " + " · ".join(f"{s[:3]} {p} {v:+.0%}" for (s, p), v in d.items()))
if all(abs(v) <= 0.10 for v in d.values()):
    print("사전 기준: 손절 방식 영향 작음 — 운영 CAP-HLD-02 선언 가능")
elif all(min(d[(s, p)] for p in ("학습", "확인")) < -0.10 for s in ("BTCUSDT", "ETHUSDT")):
    print("사전 기준: CAP-HLD-02 선언하지 않고 종가 판정 손절 유지 권고")
else:
    print("사전 기준: 둘 다 보고(혼재)")

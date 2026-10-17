"""I. 체결 지연 민감도 — v1 일봉(23시 판정)의 체결을 다음 날 h시 봉 시가로. 정보(기준 없음).
사전 등록: research/2026-10-18-overnight-design.md I.
"""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import FULL, Data, simulate, v1  # noqa: E402

for sym in sys.argv[1:] or ["BTCUSDT"]:
    D = Data(sym)
    print(f"[{sym}] 체결 지연(다음 날 h시 시가) — 수익·MDD·비율·거래")
    for h in (0, 1, 2, 4, 8, 12):
        r = simulate(D, v1(False), *FULL, 0.0005, exec_hour=h)
        print(f"  h={h:2d}: {r['ret']:+8.0%} MDD {r['mdd']:5.1%} 비율 {r['ratio']:.2f} 거래 {r['trades']}")

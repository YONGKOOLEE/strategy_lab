"""R. 2종목 반반(K) 일봉 경계 24가지. 사전 등록: research/2026-10-18-overnight-design.md R."""
from __future__ import annotations

import statistics as st
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import CONF, TRAIN, Data  # noqa: E402
from crypto_two_coin_hourly import half_curve, metrics  # noqa: E402

res = {"A-h": {"학습": [], "후기": []}, "일봉 v1": {"학습": [], "후기": []}}
for off in range(24):
    Ds = [Data(s, offset=off) for s in ("BTCUSDT", "ETHUSDT")]
    for name, (h, g) in (("A-h", (True, True)), ("일봉 v1", (False, False))):
        for pn, (s, e) in (("학습", TRAIN), ("후기", CONF)):
            parts = [half_curve(D, h, g, s, e)[0] for D in Ds]
            days = sorted(set(parts[0]) & set(parts[1]))
            res[name][pn].append(metrics({d: parts[0][d] + parts[1][d] for d in days}, s, e)["ratio"])
for name, r in res.items():
    print(f"{name:7s}: " + " | ".join(f"{pn} 최소 {min(v):.2f} 중앙 {st.median(v):.2f} 최대 {max(v):.2f}" for pn, v in r.items()))
wins = {pn: sum(a > b for a, b in zip(res['A-h'][pn], res['일봉 v1'][pn])) for pn in ("학습", "후기")}
ok = all(st.median(res["A-h"][p]) > st.median(res["일봉 v1"][p]) for p in ("학습", "후기"))
print(f"경계별 A-h 우위(24 중): {wins} · 사전 기준: {'2종목 묶음 우위 경계와 무관' if ok else '주의 표시 유지'}")

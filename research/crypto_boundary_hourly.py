"""O. 1시간판(A-h) 일봉 경계 24가지 — BTC·ETH, 일봉 v1과 비교. 사전 등록: research/2026-10-18-overnight-design.md O."""
from __future__ import annotations

import json
import statistics as st
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import CONF, TRAIN, Data, simulate, v1  # noqa: E402

out = {}
for sym in ("BTCUSDT", "ETHUSDT"):
    rows = {"A-h": {"학습": [], "확인": []}, "v1 일봉": {"학습": [], "확인": []}}
    for off in range(24):
        D = Data(sym, offset=off)
        for name, fn in (("A-h", v1(True, gate=True)), ("v1 일봉", v1(False))):
            for pn, (s, e) in (("학습", TRAIN), ("확인", CONF)):
                rows[name][pn].append(simulate(D, fn, s, e, 0.0005)["ratio"])
    out[sym] = rows
    for name, r in rows.items():
        print(f"{sym} {name:7s}: " + " | ".join(f"{pn} 최소 {min(v):.2f} 중앙 {st.median(v):.2f} 최대 {max(v):.2f}" for pn, v in r.items()))
ok = all(st.median(out[s]["A-h"][p]) > st.median(out[s]["v1 일봉"][p]) for s in out for p in ("학습", "확인"))
wins = {s: {p: sum(1 for a, b in zip(out[s]["A-h"][p], out[s]["v1 일봉"][p]) if a > b) for p in ("학습", "확인")} for s in out}
print(f"경계별 A-h > v1 일봉 개수(24 중): {wins}")
print(f"사전 기준: {'1시간판 우위가 경계와 무관(견고)' if ok else 'UTC00 결과에 기댐 — 후보 표시에 주의 추가'}")
(LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-boundary-hourly.json").write_text(json.dumps({"rows": out, "wins": wins, "ok": ok}, ensure_ascii=False), encoding="utf-8")

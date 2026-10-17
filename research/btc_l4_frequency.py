"""③ 보충 — 일일 손실 한도(L4)가 실제로 얼마나 자주 걸릴지(1시간 봉 근사). 판정 아님.

이유: 운영 M2 백테스트는 일일 손실을 판정 시각(UTC 00:15) 한 번만 재서(기준 00:00과 거의 같은 가격) K2가 구조상 0이다(2026-10-18 00:24 확인).
방법: v1(cryptosim, 25·50·ATR2 종가 손절·위험 5%·최대 98%)의 보유일마다 그날 UTC 00:00 자산 대비 장중 최저 자산(1시간 저가, 보유 수량 고정)의
손실률을 계산해, L4 값별로 '장중에 한 번이라도 넘은 날' 수를 센다. 실제 운영은 보유 중 시세 감시 간격·K2 동작(신규 진입만 막음)에 따라 다르다.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
sys.path.insert(0, str(LAB / "research"))
import cryptosim as cs  # noqa: E402
from btc_monitor_study import load_hours  # noqa: E402

V1 = dict(entry_rule="breakout", entry_n=25, exit_mode="sma", exit_n=50, stop_mode="atr", stop_atr=2.0, stop_when="close",
          risk_ratio=0.05, max_weight=0.98)


def main() -> int:
    rows = cs.load_csv(LAB / "data" / "crypto" / "BTCUSDT-1d.csv")
    r = cs.simulate(rows, dict(cs.DEFAULTS, **V1), date(2017, 9, 1), date(2025, 12, 31))
    eq = {d: v for d, v in r["eq_curve"]}
    hours = load_hours(LAB / "data" / "crypto" / "BTCUSDT-1h.csv")
    low = defaultdict(lambda: float("inf"))
    opn = {}
    for t, o, h, l, c, v in hours:
        d = t.date()
        low[d] = min(low[d], l)
        opn.setdefault(d, o)
    days = sorted(eq)
    held = []   # (날짜, 비중, 장중 최저 손실률)
    for e_day, x_day, epx, xpx, qty, why in r["trade_list"]:
        a, b = date.fromisoformat(e_day), date.fromisoformat(x_day)
        for d in days:
            ds = date.fromisoformat(d)
            if a < ds < b and ds in opn:                 # 체결일·청산일 제외(그날은 일부 시간만 보유)
                prev = days[days.index(d) - 1]
                w = qty * opn[ds] / eq[prev] if eq[prev] > 0 else 0.0
                held.append((ds, w, w * (low[ds] / opn[ds] - 1)))
    n = len(held)
    print(f"v1 보유일 {n}일(2017-09~2025, 체결·청산일 제외) · 평균 비중 {sum(h[1] for h in held) / n:.0%} · 판정 아님")
    for l4 in (0.01, 0.02, 0.03, 0.05, 0.10):
        k = sum(1 for h in held if h[2] <= -l4)
        print(f"  L4 {l4:.0%}: 장중에 넘은 날 {k}일 ({k / n:.0%}) · 연평균 {k / 8.33:.0f}일")
    return 0


if __name__ == "__main__":
    sys.exit(main())

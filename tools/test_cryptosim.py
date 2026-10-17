"""cryptosim 동작 시험 — 합성 일봉으로 진입·장중 손절(시가 갭·손절선)·SMA 청산·비용·최소 주문을 확인한다."""

from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cryptosim as cs  # noqa: E402

D0 = date(2020, 1, 1)


def write(tmp: Path, closes: list[float], lows: dict[int, float] | None = None, opens: dict[int, float] | None = None) -> Path:
    p = tmp / "x.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        prev = closes[0]
        for k, c in enumerate(closes):
            o = (opens or {}).get(k, prev)
            lo = (lows or {}).get(k, min(o, c) * 0.999)
            w.writerow([(D0 + timedelta(days=k)).isoformat(), o, max(o, c) * 1.001, lo, c, 100])
            prev = c
    return p


def run(p: Path, **kw) -> dict:
    P = dict(cs.DEFAULTS)
    P.update({"entry_n": 5, "exit_n": 5, "regime_n": 0, "slip": 0.0, "fee": 0.0, "risk_ratio": 1.0, "max_weight": 1.0})
    P.update(kw)
    rows = cs.load_csv(p)
    return cs.simulate(rows, P, rows[0][0], rows[-1][0])


def test_breakout_entry_next_open_and_sma_exit(tmp_path: Path) -> None:
    closes = [100] * 20 + [101, 103, 106, 110, 115, 120, 118, 110, 100, 95]
    r = run(write(tmp_path, closes), stop_when="close", stop_pct=0.5)
    t = r["trade_list"][0]
    assert t[0] == (D0 + timedelta(days=21)).isoformat()        # 20일째 종가 돌파 → 다음 봉 시가 체결
    assert t[5] == "sma"


def test_intraday_stop_at_stop_price(tmp_path: Path) -> None:
    closes = [100] * 20 + [101, 102, 103, 104, 105]
    p = write(tmp_path, closes, lows={23: 80.0})                  # 진입(21일 시가 101) 뒤 23일 저가가 손절선 아래
    r = run(p, stop_when="intraday", stop_pct=0.08)
    t = r["trade_list"][0]
    assert t[5] == "stop_intraday"
    assert abs(t[3] - round(101 * 0.92, 2)) < 0.02               # 손절선 가격(체결가 101 × 0.92)에 매도


def test_gap_below_stop_fills_at_open(tmp_path: Path) -> None:
    closes = [100] * 20 + [101, 102, 70, 71]
    p = write(tmp_path, closes, opens={22: 70.0}, lows={22: 69.0})
    r = run(p, stop_when="intraday", stop_pct=0.08)
    t = r["trade_list"][0]
    assert t[5] == "stop_intraday" and abs(t[3] - 70.0) < 0.02   # 시가가 손절선 아래 → 시가


def test_costs_reduce_result(tmp_path: Path) -> None:
    closes = [100] * 20 + [101, 103, 106, 110, 115, 120, 118, 110, 100, 95]
    p = write(tmp_path, closes)
    a = run(p, stop_when="close", stop_pct=0.5)
    b = run(p, stop_when="close", stop_pct=0.5, fee=0.001, slip=0.0005)
    assert b["final"] < a["final"]


def test_min_notional_blocks_tiny_order(tmp_path: Path) -> None:
    closes = [100] * 20 + [101, 103, 106]
    r = run(write(tmp_path, closes), cash=3.0)                   # 5 USDT 미만 → 주문 없음
    assert r["trades"] == 0 and r["final"] == 3.0


def test_pyramid_adds_units_and_raises_stop(tmp_path: Path) -> None:
    closes = [100] * 20 + [101 + 3 * i for i in range(20)]        # 꾸준한 상승 → 단위 추가
    rows_p = write(tmp_path, closes)
    kw = dict(stop_mode="pct", stop_pct=0.08, risk_ratio=0.01, max_weight=1.0, stop_when="close", exit_n=50)  # 1단위 = 비중 12.5%
    base = run(rows_p, pyr_max=1, **kw)
    pyr = run(rows_p, pyr_max=4, pyr_step=1.0, **kw)
    assert pyr["final"] > base["final"]                           # 상승장에서 단위가 늘어 더 큰 이익

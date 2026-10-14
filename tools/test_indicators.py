"""tools/indicators.py 손계산 기대값 시험. 실행:
  C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe -m pytest C:\\AI\\strategy-lab\\tools\\test_indicators.py -q
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indicators as ind  # noqa: E402

D = Decimal


@dataclass(frozen=True)
class B:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def bars(rows: list[tuple[int, int, int, int, int]]) -> list[B]:
    return [B(D(o), D(h), D(l), D(c), D(v)) for o, h, l, c, v in rows]


def test_sma() -> None:
    xs = [D(1), D(2), D(3), D(4)]
    assert ind.sma(xs, 2) == D("3.5")
    assert ind.sma(xs, 4) == D("2.5")
    assert ind.sma(xs, 5) is None
    assert ind.sma(xs, 0) is None


def test_ema_starts_with_sma_then_smooths() -> None:
    xs = [D(10), D(10), D(10), D(20)]
    # n=3: 시작 SMA=10, k=0.5 → 20*0.5 + 10*0.5 = 15
    assert ind.ema(xs, 3) == D("15")
    assert ind.ema(xs[:2], 3) is None


def test_atr_true_range() -> None:
    bs = bars([(10, 12, 9, 11, 1), (11, 13, 10, 12, 1), (12, 15, 11, 14, 1)])
    # TR2 = max(13-10, |13-11|, |10-11|) = 3 ; TR3 = max(15-11, |15-12|, |11-12|) = 4
    assert ind.true_ranges(bs) == [D(3), D(4)]
    assert ind.atr(bs, 2) == D("3.5")
    assert ind.atr(bs, 3) is None


def test_rsi_bounds() -> None:
    up = [D(1), D(2), D(3), D(4)]
    assert ind.rsi(up, 3) == D(100)
    mixed = [D(10), D(11), D(10), D(12)]   # +1, -1, +2 → up 3, down 1 → RS 3 → RSI 75
    assert ind.rsi(mixed, 3) == D(75)
    assert ind.rsi(mixed, 4) is None


def test_highest_lowest_exclude_today() -> None:
    xs = [D(5), D(7), D(6), D(9)]
    assert ind.highest(xs, 3) == D(7)          # 오늘(9) 제외, 그 전 3개 중 최고
    assert ind.highest(xs, 3, exclude_last=False) == D(9)
    assert ind.lowest(xs, 2) == D(6)
    assert ind.highest(xs, 4) is None           # 오늘 제외하면 3개뿐


def test_pct_change_and_stdev() -> None:
    xs = [D(100), D(110), D(121)]
    assert ind.pct_change(xs, 2) == D("0.21")
    assert ind.pct_change(xs, 3) is None
    s = ind.stdev([D(2), D(4), D(4), D(4), D(5), D(5), D(7), D(9)], 8)
    assert s is not None and abs(s - D("2.138089935")) < D("0.000001")


def test_rank_desc_deterministic_ties() -> None:
    r = ind.rank_desc({"b": D(2), "a": D(2), "c": D(5)})
    assert r == {"c": 1, "a": 2, "b": 3}


def test_avg_volume() -> None:
    bs = bars([(1, 1, 1, 1, 100), (1, 1, 1, 1, 300)])
    assert ind.avg_volume(bs, 2) == D(200)
    assert ind.avg_volume(bs, 3) is None

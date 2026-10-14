"""전략실 공용 지표 — 검증된 구현의 원본. 표준 라이브러리(Decimal)만 쓴다.

**사용 방식**: 후보 `strategy.py`는 이 모듈을 import하지 않는다(운영 규격: 표준 라이브러리 + trading_system.domain·strategy만).
필요한 함수를 `strategy.py`에 **그대로 복사(인라인)** 한다. 그래야 운영 저장소로 옮길 때 변환 없이 구조 시험을 통과한다.
새 지표를 여기 추가하면 `tools/test_indicators.py`에 손으로 계산한 기대값 시험을 함께 추가한다.

입력은 운영 `trading_system.domain.strategy.Bar`와 같은 속성(open·high·low·close·volume)을 가진 객체의 순서열,
또는 Decimal 목록이다. 길이가 부족하면 None을 돌려준다(전략은 None이면 신호를 내지 않는다).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol


class BarLike(Protocol):
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def closes(bars: Sequence[BarLike]) -> list[Decimal]:
    return [b.close for b in bars]


def sma(xs: Sequence[Decimal], n: int) -> Decimal | None:
    """단순 이동평균(마지막 n개)."""
    if n <= 0 or len(xs) < n:
        return None
    return sum(xs[-n:], Decimal("0")) / n


def ema(xs: Sequence[Decimal], n: int) -> Decimal | None:
    """지수 이동평균. 처음 n개의 SMA로 시작, 이후 k = 2/(n+1). 길이 < n이면 None."""
    if n <= 0 or len(xs) < n:
        return None
    k = Decimal(2) / (n + 1)
    e = sum(xs[:n], Decimal("0")) / n
    for x in xs[n:]:
        e = x * k + e * (1 - k)
    return e


def true_ranges(bars: Sequence[BarLike]) -> list[Decimal]:
    """TR = max(H−L, |H−전일C|, |L−전일C|). 첫 봉은 전일이 없어 제외 → 길이 len−1."""
    return [max(b.high - b.low, abs(b.high - p.close), abs(b.low - p.close)) for p, b in zip(bars[:-1], bars[1:])]


def atr(bars: Sequence[BarLike], n: int) -> Decimal | None:
    """ATR(n) = 마지막 n개 TR의 단순 평균. 봉 n+1개 필요."""
    if n <= 0 or len(bars) < n + 1:
        return None
    trs = true_ranges(bars[-n - 1:])
    return sum(trs, Decimal("0")) / n


def rsi(xs: Sequence[Decimal], n: int) -> Decimal | None:
    """RSI(n), 단순 평균 방식(Cutler). 하락 합이 0이면 100."""
    if n <= 0 or len(xs) < n + 1:
        return None
    ch = [b - a for a, b in zip(xs[-n - 1:-1], xs[-n:])]
    up = sum((c for c in ch if c > 0), Decimal("0"))
    down = -sum((c for c in ch if c < 0), Decimal("0"))
    if down == 0:
        return Decimal("100")
    rs = up / down
    return Decimal("100") - Decimal("100") / (1 + rs)


def highest(xs: Sequence[Decimal], n: int, *, exclude_last: bool = True) -> Decimal | None:
    """최근 n개 최고값. exclude_last=True면 마지막 값(오늘)을 빼고 그 전 n개 — 돌파 판정용(전일까지 최고)."""
    ys = xs[:-1] if exclude_last else xs
    if n <= 0 or len(ys) < n:
        return None
    return max(ys[-n:])


def lowest(xs: Sequence[Decimal], n: int, *, exclude_last: bool = True) -> Decimal | None:
    ys = xs[:-1] if exclude_last else xs
    if n <= 0 or len(ys) < n:
        return None
    return min(ys[-n:])


def pct_change(xs: Sequence[Decimal], n: int) -> Decimal | None:
    """n거래일 수익률 = 마지막 / n개 전 − 1. 0으로 나누면 None."""
    if n <= 0 or len(xs) < n + 1 or xs[-n - 1] == 0:
        return None
    return xs[-1] / xs[-n - 1] - 1


def stdev(xs: Sequence[Decimal], n: int) -> Decimal | None:
    """마지막 n개 표본 표준편차(n−1 분모). n < 2면 None."""
    if n < 2 or len(xs) < n:
        return None
    ys = list(xs[-n:])
    m = sum(ys, Decimal("0")) / n
    var = sum(((y - m) * (y - m) for y in ys), Decimal("0")) / (n - 1)
    return var.sqrt()


def avg_volume(bars: Sequence[BarLike], n: int) -> Decimal | None:
    if n <= 0 or len(bars) < n:
        return None
    return sum((b.volume for b in bars[-n:]), Decimal("0")) / n


def rank_desc(values: dict[str, Decimal]) -> dict[str, int]:
    """값 내림차순 순위(1 = 최대). 같은 값은 키 순으로 결정적으로 정렬 — 종목 간 상대강도용."""
    order = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    return {k: i + 1 for i, (k, _) in enumerate(order)}

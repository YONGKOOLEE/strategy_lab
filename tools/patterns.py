"""차트 패턴 검출기 (연구용, 표준 라이브러리·float). 컵앤핸들·VCP 근사 규칙 — research/2026-10-11-trend-patterns-cup-handle-vcp.md §3.2.

**연구 전용**: 사건 연구(research/)와 규칙 탐색에 쓴다. 후보 strategy.py에 넣을 때는 Decimal로 옮겨 인라인한다(tools/indicators.py 규칙과 같음).
모든 함수는 "판정일 t까지의 봉"만 받는다(t = 전일 봉). 미래 봉을 보지 않는다. 파라미터는 사전 고정값이며 데이터로 조정하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence


@dataclass(frozen=True)
class CupParams:
    window: int = 120          # 베이스 탐색 창(거래일)
    depth_min: float = 0.12    # 컵 깊이 하한
    depth_max: float = 0.33    # 컵 깊이 상한
    rim_ratio: float = 0.95    # 우측 림 ≥ 좌측 림 × 비율
    bottom_pos: tuple[float, float] = (0.3, 0.7)   # 바닥 위치(좌측 림~우측 림 사이 비율)
    round_tol: float = 0.03    # 바닥 전후 5일 평균이 바닥 대비 이내(둥근 바닥 근사)
    handle_len: tuple[int, int] = (5, 20)
    handle_depth: tuple[float, float] = (0.03, 0.12)
    vol_mult: float = 1.4      # 돌파일 거래량 ≥ 50일 평균 × 배수
    vol_avg_n: int = 50


@dataclass(frozen=True)
class VcpParams:
    lookback: int = 120
    zigzag: float = 0.03       # 스윙 전환 임계
    min_contractions: int = 2
    shrink: float = 0.75       # 각 수축 ≤ 직전 × 비율
    last_depth_max: float = 0.10
    dryup: float = 0.70        # 최근 10일 평균 거래량 < 50일 평균 × 비율
    vol_mult: float = 1.5
    vol_avg_n: int = 50
    tt_near_high: float = 0.75  # 52주 고점 대비 ≥ 75%
    tt_above_low: float = 1.25  # 52주 저점 대비 ≥ 125%


@dataclass(frozen=True)
class CupEvent:
    left_rim: int
    bottom: int
    right_rim: int
    handle_low: float
    pivot: float
    depth: float


@dataclass(frozen=True)
class VcpEvent:
    contractions: tuple[float, ...]
    pivot: float
    stop: float


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def sma(xs: Sequence[float], n: int) -> float | None:
    return _mean(xs[-n:]) if n > 0 and len(xs) >= n else None


# --- 컵앤핸들 ------------------------------------------------------------------------------------

def detect_cup_handle(closes: Sequence[float], volumes: Sequence[float], p: CupParams = CupParams()) -> CupEvent | None:
    """마지막 봉(t)이 핸들 고점 돌파일이면 CupEvent. 입력은 t까지의 종가·거래량(미래 없음)."""
    n = len(closes)
    if n < p.window + 1 or n < p.vol_avg_n + 1:
        return None
    c = closes[-p.window - 1:-1]       # 베이스 창: t 직전 window개 (t 제외)
    v = volumes[-p.window - 1:-1]
    L = len(c)
    hmin, hmax = p.handle_len
    # 좌측 림: 창 앞부분(핸들·우측 림 자리를 남김)에서 최고 종가
    left_end = L - hmax - 10
    if left_end <= 5:
        return None
    i = max(range(0, left_end), key=lambda k: c[k])
    H = c[i]
    # 핸들 길이 후보마다 우측 림 위치를 정해 검사(긴 핸들부터 — 림은 핸들 전체보다 높아야 함)
    for h in range(hmax, hmin - 1, -1):
        r = L - 1 - h                  # 우측 림 = 핸들 시작 직전
        if r <= i + 10:
            continue
        seg = c[i + 1:r]
        if not seg:
            continue
        j_rel = min(range(len(seg)), key=lambda k: seg[k])
        j = i + 1 + j_rel
        B = c[j]
        depth = (H - B) / H
        if not (p.depth_min <= depth <= p.depth_max):
            continue
        R = c[r]
        if R < p.rim_ratio * H or R > H * 1.05 or R < max(c[j:]):   # 우측 림 = 바닥 이후 최고점
            continue
        pos = (j - i) / (r - i)
        if not (p.bottom_pos[0] <= pos <= p.bottom_pos[1]):
            continue
        lo5, hi5 = max(i, j - 5), min(r, j + 6)
        if _mean(c[lo5:hi5]) > B * (1 + p.round_tol):
            continue
        handle = c[r + 1:]
        if len(handle) < hmin or max(handle) >= R:   # 우측 림이 핸들 구간 전체보다 높아야 림이다
            continue
        hl = min(handle)
        hd = (R - hl) / R
        if not (p.handle_depth[0] <= hd <= p.handle_depth[1]):
            continue
        if hl <= (H + B) / 2:
            continue
        if _mean(v[r + 1:]) >= _mean(v[i:r + 1]):
            continue
        pivot = max(handle)
        if closes[-1] <= pivot:
            continue
        va = sma(volumes[:-1], p.vol_avg_n)
        if va is None or volumes[-1] < p.vol_mult * va:
            continue
        return CupEvent(i, j, r, hl, pivot, depth)
    return None


# --- VCP -------------------------------------------------------------------------------------------

def zigzag(closes: Sequence[float], threshold: float) -> list[tuple[int, float, str]]:
    """종가 지그재그 스윙 (index, price, 'H'|'L'). 전환은 직전 극값 대비 threshold 이상 반대 이동."""
    if not closes:
        return []
    piv: list[tuple[int, float, str]] = []
    # 초기 추세 결정: 시작 뒤 최고·최저를 따로 추적, 어느 쪽으로 threshold 이상 되돌리면 첫 극값 확정
    hi_i, hi_p, lo_i, lo_p = 0, closes[0], 0, closes[0]
    trend = 0
    ext_i, ext_p = 0, closes[0]
    k = 1
    while k < len(closes) and trend == 0:
        x = closes[k]
        if x > hi_p:
            hi_i, hi_p = k, x
        if x < lo_p:
            lo_i, lo_p = k, x
        if x <= hi_p * (1 - threshold):
            piv.append((hi_i, hi_p, "H"))
            trend, ext_i, ext_p = -1, k, x
        elif x >= lo_p * (1 + threshold):
            piv.append((lo_i, lo_p, "L"))
            trend, ext_i, ext_p = 1, k, x
        k += 1
    for k in range(k, len(closes)):
        x = closes[k]
        if trend == 1 and x > ext_p:
            ext_i, ext_p = k, x
        elif trend == -1 and x < ext_p:
            ext_i, ext_p = k, x
        if trend == 1 and x <= ext_p * (1 - threshold):
            piv.append((ext_i, ext_p, "H"))
            trend, ext_i, ext_p = -1, k, x
        elif trend == -1 and x >= ext_p * (1 + threshold):
            piv.append((ext_i, ext_p, "L"))
            trend, ext_i, ext_p = 1, k, x
    return piv


def trend_template(closes: Sequence[float], p: VcpParams = VcpParams()) -> bool:
    """Minervini Trend Template 7항(EPS 제외) — 종가 기반 근사. 250거래일 필요."""
    if len(closes) < 250 + 21:
        return False
    c = closes[-1]
    s50, s150, s200 = sma(closes, 50), sma(closes, 150), sma(closes, 200)
    s200_prev = sma(closes[:-21], 200)
    if None in (s50, s150, s200, s200_prev):
        return False
    yr = closes[-250:]
    return (c > s150 and c > s200 and s150 > s200 and s200 > s200_prev and s50 > s150 and s50 > s200 and c > s50
            and c >= p.tt_above_low * min(yr) and c >= p.tt_near_high * max(yr))


def detect_vcp(closes: Sequence[float], volumes: Sequence[float], p: VcpParams = VcpParams()) -> VcpEvent | None:
    """마지막 봉(t)이 마지막 수축 고점 돌파일이면 VcpEvent. 추세 템플릿은 t−1 기준(돌파 전 상태)."""
    if len(closes) < max(p.lookback, 271) + 1:
        return None
    if not trend_template(closes[:-1], p):
        return None
    base = closes[-p.lookback - 1:-1]
    piv = zigzag(base, p.zigzag)
    # 수축 = 스윙 고점 → 다음 스윙 저점 깊이
    deps: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    for a, b in zip(piv, piv[1:]):
        if a[2] == "H" and b[2] == "L":
            deps.append((a[1] - b[1]) / a[1])
            highs.append(a[1])
            lows.append(b[1])
    if len(deps) < p.min_contractions:
        return None
    k = len(deps)
    m = 1
    while m < k and deps[k - m] <= p.shrink * deps[k - m - 1]:
        m += 1
    if m < p.min_contractions or deps[-1] > p.last_depth_max:
        return None
    pivot, stop = highs[-1], lows[-1]
    if base[-1] > pivot:                      # 이미 돌파 상태였으면 첫 돌파일이 아님
        return None
    if closes[-1] <= pivot:
        return None
    v = volumes
    v10, v50 = sma(v[:-1], 10), sma(v[:-1], p.vol_avg_n)
    if v10 is None or v50 is None or v10 >= p.dryup * v50:
        return None
    if v[-1] < p.vol_mult * v50:
        return None
    return VcpEvent(tuple(deps[-m:]), pivot, stop)

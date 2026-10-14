"""tools/patterns.py 손계산 시험. 실행:
  C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe -m pytest C:\\AI\\strategy-lab\\tools\\test_patterns.py -q -p no:cacheprovider
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patterns as pt  # noqa: E402


def test_zigzag_basic() -> None:
    xs = [100, 110, 120, 110, 100, 108, 116, 112, 108, 120]
    piv = pt.zigzag(xs, 0.05)
    kinds = [k for _, _, k in piv]
    # 시작 100(L) → 120(H) → 100(L) → 116(H) → 108(L) : 마지막 120은 미확정이라 없음
    assert kinds == ["L", "H", "L", "H", "L"]
    assert [p for _, p, _ in piv] == [100, 120, 100, 116, 108]


def _synthetic_cup(window: int = 120) -> tuple[list[float], list[float]]:
    """좌측 림 100 → 바닥 80(깊이 20%) → 우측 림 98 → 핸들 저점 92(깊이 6%) → 돌파 100."""
    up = [60 + i for i in range(20)]                 # 선행 상승 → 79..
    left = [100.0]
    down = [100 - (20 * k / 45) for k in range(1, 46)]   # 45일 하락 → 80
    bottom = [80.0] * 6
    rise = [80 + (18 * k / 45) for k in range(1, 46)]    # 45일 상승 → 98
    handle = [98 - (6 * k / 6) for k in range(1, 7)] + [92.5, 93, 93.5, 94]   # 10일 핸들, 저점 92
    closes = up + left + down + bottom + rise + handle
    vols = [1000.0] * len(closes)
    for k in range(len(handle)):                      # 핸들 거래량 감소
        vols[-len(handle) + k] = 500.0
    closes.append(101.0)                              # 돌파일: 핸들 고점(97) 위
    vols.append(2000.0)                               # 50일 평균(≈900) × 1.4 이상
    return closes, vols


def test_cup_handle_detects_synthetic() -> None:
    closes, vols = _synthetic_cup()
    ev = pt.detect_cup_handle(closes, vols)
    assert ev is not None
    assert abs(ev.depth - 0.20) < 0.01
    assert ev.handle_low == 92.0
    assert ev.pivot == 97.0


def test_cup_handle_rejects_without_volume_or_breakout() -> None:
    closes, vols = _synthetic_cup()
    vols[-1] = 900.0                                  # 거래량 미달
    assert pt.detect_cup_handle(closes, vols) is None
    closes2, vols2 = _synthetic_cup()
    closes2[-1] = 96.0                                # 피벗 미돌파
    assert pt.detect_cup_handle(closes2, vols2) is None


def test_trend_template_requires_history_and_alignment() -> None:
    rising = [100 + 0.2 * i for i in range(300)]
    assert pt.trend_template(rising)
    falling = [200 - 0.2 * i for i in range(300)]
    assert not pt.trend_template(falling)
    assert not pt.trend_template(rising[:200])


def test_vcp_detects_synthetic_contractions() -> None:
    # 300일 상승 추세 뒤 수축 3회(20%→10%→5%)와 거래량 고갈, 돌파
    closes = [50 + 0.25 * i for i in range(300)]      # 끝 ≈ 124.75
    top = closes[-1]
    def leg(a: float, b: float, n: int) -> list[float]:
        return [a + (b - a) * k / n for k in range(1, n + 1)]
    seq = leg(top, top * 0.80, 15) + leg(top * 0.80, top, 15) + leg(top, top * 0.90, 10) + leg(top * 0.90, top, 10) \
        + leg(top, top * 0.95, 6) + leg(top * 0.95, top * 0.995, 6)
    closes += seq
    vols = [1000.0] * len(closes)
    for k in range(1, 11):
        vols[-k] = 400.0                              # 최근 10일 고갈
    closes.append(top * 1.02)                         # 돌파
    vols.append(1800.0)
    ev = pt.detect_vcp(closes, vols)
    assert ev is not None
    assert len(ev.contractions) >= 2
    assert ev.contractions[-1] <= 0.10
    assert ev.pivot <= top + 1e-9

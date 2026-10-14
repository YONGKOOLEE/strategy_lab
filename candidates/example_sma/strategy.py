"""예시 후보 example-sma v1 — 전략실 사용법을 보여 주는 견본. **실전 후보 아님.**

새 후보는 `/new-candidate <이름>`으로 이 폴더를 복사해 만든다(CLAUDE.md §4). 이 파일은 **자기완결**이다:
표준 라이브러리 + trading_system.domain·trading_system.strategy.base만 import하고, 지표·크기 도우미는 아래에 인라인한다
(원본: tools/indicators.py). 그래야 운영 저장소로 그대로 복사해도 구조 시험을 통과한다.

규칙 (판정 1일 1회, 전일까지 확정 일봉 종가 기준. 종목마다 신호 최대 1개, 청산 > 진입):
- EXIT-1 : 보유 AND SMA(fast) <= SMA(slow) → 전량 시장가 청산.
- ENTRY-1: 보유 없음 AND SMA(fast) > SMA(slow) → 시장가 진입. 손절가 = 종가 − atr_mult×ATR(14)(크기 계산용, 장중 손절 주문 없음).
순수 함수: 스냅샷과 파라미터만 본다. 파일·네트워크·현재 시각을 쓰지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from trading_system.domain.enums import OrderType, RequestType
from trading_system.domain.models import Signal
from trading_system.domain.sizing import round_price_down, size_fixed_amount, size_ratio, size_risk
from trading_system.domain.strategy import (
    Bar, EvaluationSnapshot, InstrumentView, ParamSpec, RuleSpec, StrategyLimits, StrategySpec)
from trading_system.strategy.base import ParamValues, make_signal

STRATEGY_ID = "example-sma"
VERSION = 1
_INPUTS = ("CAP-DAT-01", "상태 입력")
_ATR_N = 14
VALID_FOR = timedelta(minutes=10)
WORST_PRICE_FACTOR = Decimal("1.3")   # 게이트는 시장가 매수 금액을 상한가(×1.3)로 평가한다
L7_AMOUNT = Decimal("1000000")        # 1회 주문 금액 상한 = 계좌 L7 (운영 A-034)


# --- 지표 (tools/indicators.py에서 복사, 수정 금지 — 바꾸려면 원본과 시험을 먼저 고친다) -----------------

def _sma(xs: Sequence[Decimal], n: int) -> Decimal | None:
    if n <= 0 or len(xs) < n:
        return None
    return sum(xs[-n:], Decimal("0")) / n


def _atr(bars: Sequence[Bar], n: int) -> Decimal | None:
    if n <= 0 or len(bars) < n + 1:
        return None
    window = bars[-n - 1:]
    trs = [max(b.high - b.low, abs(b.high - p.close), abs(b.low - p.close)) for p, b in zip(window[:-1], window[1:])]
    return sum(trs, Decimal("0")) / n


# --- 공통 도우미 (크기·신호) --------------------------------------------------------------------

def _ready(v: InstrumentView, universe: tuple[str, ...]) -> bool:
    return v.instrument in universe and v.data_ok and not v.has_pending_order and bool(v.daily_bars)


def _held(v: InstrumentView) -> bool:
    return v.position is not None and v.position.owned_by_me and v.position.quantity > 0


def _size(snapshot: EvaluationSnapshot, params: ParamValues, price: Decimal, stop: Decimal) -> Decimal:
    """S-3: min(위험 기반, 종목 비중 상한, L7 상한가 기준)."""
    base = snapshot.base_amount
    by_risk = size_risk(base * Decimal(str(params["risk_ratio"])), price, stop)
    by_weight = size_ratio(base, Decimal(str(params["max_weight"])), price)
    by_l7 = size_fixed_amount(L7_AMOUNT, price * WORST_PRICE_FACTOR)
    return min(by_risk, by_weight, by_l7)


def _entry(spec: StrategySpec, snapshot: EvaluationSnapshot, params: ParamValues, v: InstrumentView,
           rule: str, stop: Decimal) -> Signal | None:
    if v.statuses:            # 거래 상태 이상(정지·VI 등)이면 진입하지 않음
        return None
    price = v.last_price if v.last_price is not None else v.daily_bars[-1].close
    if stop <= 0 or stop >= price:
        return None
    qty = _size(snapshot, params, price, stop)
    if qty <= 0:
        return None
    return make_signal(spec, snapshot, v.instrument, rule, RequestType.ENTRY, qty, OrderType.MARKET, price, VALID_FOR,
                       stop_price=stop)


def _exit(spec: StrategySpec, snapshot: EvaluationSnapshot, v: InstrumentView, rule: str) -> Signal:
    price = v.last_price if v.last_price is not None else v.daily_bars[-1].close
    assert v.position is not None
    return make_signal(spec, snapshot, v.instrument, rule, RequestType.EXIT, v.position.quantity, OrderType.MARKET,
                       price, VALID_FOR)


# --- 명세 -----------------------------------------------------------------------------------------

def build_spec() -> StrategySpec:
    rules = (
        RuleSpec("EXIT-1", "EXIT", _INPUTS, "CAP-TRG-01", "보유 AND SMA(fast) <= SMA(slow)",
                 "청산 전량 시장가", "데이터 품질 실패·처리 중 주문", 1),
        RuleSpec("ENTRY-1", "ENTRY", _INPUTS, "CAP-TRG-01", "보유 없음 AND SMA(fast) > SMA(slow)",
                 "진입 S-3 시장가(손절가 = 종가 − atr_mult×ATR14)", "데이터 품질 실패·거래 상태 이상·처리 중 주문", 1),
    )
    params = (
        ParamSpec("fast", "int", "거래일", "단기 이동평균 (fast < slow)", Decimal("3"), Decimal("50")),
        ParamSpec("slow", "int", "거래일", "장기 이동평균", Decimal("10"), Decimal("200")),
        ParamSpec("atr_mult", "decimal", "배", "크기 계산용 손절 ATR 배수", Decimal("1"), Decimal("5")),
        ParamSpec("risk_ratio", "decimal", "비율", "1회 위험 = 기준 금액 × 값 (L1 0.5% 이하)", Decimal("0.001"), Decimal("0.005")),
        ParamSpec("max_weight", "decimal", "비율", "종목 비중 상한 (L2 10% 이하)", Decimal("0.01"), Decimal("0.10")),
    )
    return StrategySpec(
        strategy_id=STRATEGY_ID, name="예시 이동평균 교차", version=VERSION,
        description="전략실 견본(실전 후보 아님)",
        markets=("M1",), universe_method="U-A", universe=("005930",),   # 전략실 실행기는 데이터 폴더 종목으로 바꿔 실행
        capabilities=("CAP-TRG-01", "CAP-DAT-01", "CAP-ORD-01", "CAP-INS-01"),
        data_requirements="일봉 OHLC 수정주가, 워밍업 max(slow, 15)거래일",
        trigger="CAP-TRG-01 배포 설정 eval_times (1일 1회)", rules=rules, params=params,
        signal_format="00 §2.5", validity_rule="판정 기준 시각 + 10분", validity_max_minutes=10,
        unfilled_policy="시스템 기본", sizing="S-3", holding="수일~수개월, 최대 보유 제한 없음",
        limits=StrategyLimits(l7_max_order_amount=L7_AMOUNT),
    )


class ExampleSmaV1:
    def __init__(self) -> None:
        self.spec = build_spec()

    def evaluate(self, snapshot: EvaluationSnapshot, params: ParamValues) -> list[Signal]:
        fast, slow = int(str(params["fast"])), int(str(params["slow"]))
        mult = Decimal(str(params["atr_mult"]))
        if fast >= slow:
            raise ValueError("example-sma: fast < slow 이어야 한다")
        out: list[Signal] = []
        for v in snapshot.instruments:
            if not _ready(v, self.spec.universe):
                continue
            xs = [b.close for b in v.daily_bars]
            f, s, atr = _sma(xs, fast), _sma(xs, slow), _atr(v.daily_bars, _ATR_N)
            if f is None or s is None or atr is None:
                continue
            if _held(v):
                if f <= s:
                    out.append(_exit(self.spec, snapshot, v, "EXIT-1"))
            elif v.position is None or v.position.quantity == 0:
                if f > s:
                    stop = round_price_down(xs[-1] - mult * atr, Decimal("1"))
                    sig = _entry(self.spec, snapshot, params, v, "ENTRY-1", stop)
                    if sig is not None:
                        out.append(sig)
        return out

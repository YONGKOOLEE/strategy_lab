"""후보 rsi2-meanrev v1 — 상승 추세(종가 > SMA(trend_n)) 종목의 RSI(2) 과매도 되돌림. 전략실 연구 후보(운영 미등록).

규칙 (판정 1일 1회 09:30, 전일까지 확정 일봉 기준. 종목마다 신호 최대 1개, 청산 > 진입):
- 평가 가능 종목 = 유니버스 안 · 품질 통과 · 처리 중 주문 없음 · 일봉 ≥ max(trend_n, 6).
- EXIT-1 : 보유 AND (종가 > SMA(5) OR 보유 거래일 >= hold_max OR 종가 < 평균 매입가 × (1 − stop_pct)) → 전량 시장가 청산.
- ENTRY-1: 보유 종목 수 < TOP_N(3) 일 때, 미보유 AND 종가 > SMA(trend_n) AND RSI(2) < rsi_entry 인 종목을
           RSI 낮은 순으로 **빈 슬롯 수만큼만** 시장가 진입. 손절가 = 종가 × (1 − stop_pct)(크기 계산용).
순수 함수: 스냅샷과 파라미터만 본다. 파일·네트워크·현재 시각·난수 없음. 지표는 tools/indicators.py에서 복사(인라인).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from trading_system.domain.enums import OrderType, RequestType
from trading_system.domain.models import Signal
from trading_system.domain.sizing import round_price_down, size_fixed_amount, size_ratio, size_risk
from trading_system.domain.strategy import (
    EvaluationSnapshot, InstrumentView, ParamSpec, RuleSpec, StrategyLimits, StrategySpec)
from trading_system.strategy.base import ParamValues, make_signal

STRATEGY_ID = "rsi2-meanrev"
VERSION = 1
TOP_N = 3                             # 보유 상한 = 계좌 L6
_RSI_N = 2
_EXIT_SMA_N = 5
_INPUTS = ("CAP-DAT-01", "상태 입력")
VALID_FOR = timedelta(minutes=10)
WORST_PRICE_FACTOR = Decimal("1.3")


# --- 지표 (tools/indicators.py에서 복사, 수정 금지) -------------------------------------------------

def _sma(xs: Sequence[Decimal], n: int) -> Decimal | None:
    if n <= 0 or len(xs) < n:
        return None
    return sum(xs[-n:], Decimal("0")) / n


def _rsi(xs: Sequence[Decimal], n: int) -> Decimal | None:
    if n <= 0 or len(xs) < n + 1:
        return None
    ch = [b - a for a, b in zip(xs[-n - 1:-1], xs[-n:])]
    up = sum((c for c in ch if c > 0), Decimal("0"))
    down = -sum((c for c in ch if c < 0), Decimal("0"))
    if down == 0:
        return Decimal("100")
    rs = up / down
    return Decimal("100") - Decimal("100") / (1 + rs)


# --- 공통 도우미 ------------------------------------------------------------------------------------

def _ready(v: InstrumentView, universe: tuple[str, ...]) -> bool:
    return v.instrument in universe and v.data_ok and not v.has_pending_order and bool(v.daily_bars)


def _held(v: InstrumentView) -> bool:
    return v.position is not None and v.position.owned_by_me and v.position.quantity > 0


def _size(snapshot: EvaluationSnapshot, params: ParamValues, price: Decimal, stop: Decimal) -> Decimal:
    base = snapshot.base_amount
    by_risk = size_risk(base * Decimal(str(params["risk_ratio"])), price, stop)
    by_weight = size_ratio(base, Decimal(str(params["max_weight"])), price)
    by_cap = size_fixed_amount(Decimal(str(params["order_cap"])), price * WORST_PRICE_FACTOR)
    return min(by_risk, by_weight, by_cap)


def _entry(spec: StrategySpec, snapshot: EvaluationSnapshot, params: ParamValues, v: InstrumentView,
           rule: str, stop: Decimal) -> Signal | None:
    if v.statuses:
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
        RuleSpec("EXIT-1", "EXIT", _INPUTS, "CAP-TRG-01",
                 "보유 AND (종가 > SMA(5) OR 보유 거래일 >= hold_max OR 종가 < 평균 매입가 × (1 − stop_pct))",
                 "청산 전량 시장가", "데이터 품질 실패·처리 중 주문", 1),
        RuleSpec("ENTRY-1", "ENTRY", _INPUTS, "CAP-TRG-01",
                 "보유 종목 수 < 3 AND 미보유 AND 종가 > SMA(trend_n) AND RSI(2) < rsi_entry — RSI 낮은 순으로 빈 슬롯 수만큼",
                 "진입 S-3 시장가(손절가 = 종가 × (1 − stop_pct))", "데이터 품질 실패·거래 상태 이상·처리 중 주문", 1),
    )
    params = (
        ParamSpec("trend_n", "int", "거래일", "추세 필터 SMA 기간", Decimal("50"), Decimal("200")),
        ParamSpec("rsi_entry", "int", "RSI", "RSI(2) 진입 기준(미만)", Decimal("5"), Decimal("30")),
        ParamSpec("hold_max", "int", "거래일", "최대 보유 거래일(도달 시 청산)", Decimal("2"), Decimal("15")),
        ParamSpec("stop_pct", "decimal", "비율", "손절 비율(평균 매입가 대비, 종가 판정)", Decimal("0.02"), Decimal("0.10")),
        ParamSpec("risk_ratio", "decimal", "비율", "1회 위험 = 기준 금액 × 값 (L1 0.5% 이하)", Decimal("0.001"), Decimal("0.005")),
        ParamSpec("max_weight", "decimal", "비율", "종목 비중 상한 (L2 10% 이하)", Decimal("0.01"), Decimal("0.10")),
        ParamSpec("order_cap", "decimal", "원", "1회 주문 금액 상한(상한가 기준 환산, 계좌 L7 이하)", Decimal("100000"), Decimal("50000000")),
    )
    return StrategySpec(
        strategy_id=STRATEGY_ID, name="RSI(2) 단기 되돌림", version=VERSION,
        description="종가 > SMA(trend_n) AND RSI(2) < rsi_entry 진입, 종가 > SMA(5)·hold_max·손절 청산, 빈 슬롯은 RSI 낮은 순 — 전략실 연구 후보(운영 미등록)",
        markets=("M1",), universe_method="U-A", universe=("005930",),
        capabilities=("CAP-TRG-01", "CAP-DAT-01", "CAP-ORD-01", "CAP-INS-01"),
        data_requirements="일봉 OHLC 수정주가, 워밍업 max(trend_n, 6) 거래일(종목별)",
        trigger="CAP-TRG-01 배포 설정 eval_times (1일 1회, 09:30)", rules=rules, params=params,
        signal_format="00 §2.5", validity_rule="판정 기준 시각 + 10분", validity_max_minutes=10,
        unfilled_policy="시스템 기본", sizing="S-3", holding="1~hold_max 거래일(최대 보유 제한 = hold_max)",
        limits=StrategyLimits(),
    )


class Rsi2MeanrevV1:
    def __init__(self) -> None:
        self.spec = build_spec()

    def evaluate(self, snapshot: EvaluationSnapshot, params: ParamValues) -> list[Signal]:
        trend_n, rsi_entry = int(str(params["trend_n"])), int(str(params["rsi_entry"]))
        hold_max, stop_pct = int(str(params["hold_max"])), Decimal(str(params["stop_pct"]))
        warmup = max(trend_n, _EXIT_SMA_N + 1, _RSI_N + 1)

        out: list[Signal] = []
        candidates: list[tuple[Decimal, str, InstrumentView, Decimal]] = []   # (RSI, 코드, 뷰, 손절가)
        for v in snapshot.instruments:
            if not _ready(v, self.spec.universe) or len(v.daily_bars) < warmup:
                continue
            xs = [b.close for b in v.daily_bars]
            close = xs[-1]
            if _held(v):
                assert v.position is not None
                sma5 = _sma(xs, _EXIT_SMA_N)
                stop_line = v.position.avg_price * (1 - stop_pct)
                if sma5 is None:
                    continue
                if close > sma5 or v.position.holding_days >= hold_max or close < stop_line:
                    out.append(_exit(self.spec, snapshot, v, "EXIT-1"))
            elif v.position is None or v.position.quantity == 0:
                trend, rsi = _sma(xs, trend_n), _rsi(xs, _RSI_N)
                if trend is None or rsi is None:
                    continue
                if close > trend and rsi < rsi_entry:
                    stop = round_price_down(close * (1 - stop_pct), Decimal("1"))
                    candidates.append((rsi, v.instrument, v, stop))

        held_total = sum(1 for v in snapshot.instruments if _held(v))
        free = TOP_N - held_total
        if free <= 0:
            return out
        for _rsi_v, _code, v, stop in sorted(candidates, key=lambda t: (t[0], t[1])):
            if free <= 0:
                break
            sig = _entry(self.spec, snapshot, params, v, "ENTRY-1", stop)
            if sig is not None:
                out.append(sig)
                free -= 1
        return out

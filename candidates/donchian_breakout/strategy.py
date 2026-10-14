"""후보 donchian-breakout v1 — 20일 최고 종가 돌파 진입, 10일 최저 종가 이탈 청산. 전략실 연구 후보(운영 미등록).

규칙 (판정 1일 1회 09:30, 전일까지 확정 일봉 기준. 종목마다 신호 최대 1개, 청산 > 진입):
- 09:30 판정 시 스냅샷의 마지막 봉(daily_bars[-1])은 **전일** 봉이다. 아래 "전일 이전 n거래일" = 그 전일 봉을 뺀 n개.
- 평가 가능 종목 = 유니버스 안 · 품질 통과 · 처리 중 주문 없음 · 일봉 ≥ max(entry_n, exit_n) + 1.
- EXIT-1 : 보유 AND 전일 종가 <= 전일 이전 exit_n거래일 최저 종가 → 전량 시장가 청산.
- ENTRY-1: 보유 종목 수 < TOP_N(3) 일 때, 미보유 AND 전일 종가 > 전일 이전 entry_n거래일 최고 종가 인 종목을
           돌파 강도(전일 종가/최고 − 1) 큰 순으로 **빈 슬롯 수만큼만** 시장가 진입. 손절가 = 전일 이전 exit_n거래일 최저 종가(크기 계산용).
           09:30 기준가(시가)가 손절가 이하면 진입 없음. 당일 청산으로 비는 슬롯은 다음 판정부터 채운다.
순수 함수: 스냅샷과 파라미터만 본다. 파일·네트워크·현재 시각·난수 없음. 지표는 tools/indicators.py에서 복사(인라인).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from trading_system.domain.enums import OrderType, RequestType
from trading_system.domain.models import Signal
from trading_system.domain.sizing import size_fixed_amount, size_ratio, size_risk
from trading_system.domain.strategy import (
    EvaluationSnapshot, InstrumentView, ParamSpec, RuleSpec, StrategyLimits, StrategySpec)
from trading_system.strategy.base import ParamValues, make_signal

STRATEGY_ID = "donchian-breakout"
VERSION = 1
TOP_N = 3                             # 보유 상한 = 계좌 L6
_INPUTS = ("CAP-DAT-01", "상태 입력")
VALID_FOR = timedelta(minutes=10)
WORST_PRICE_FACTOR = Decimal("1.3")   # 게이트는 시장가 매수 금액을 상한가(×1.3)로 평가한다


# --- 지표 (tools/indicators.py에서 복사, 수정 금지) -------------------------------------------------

def _highest(xs: Sequence[Decimal], n: int) -> Decimal | None:
    ys = xs[:-1]                      # 마지막 봉(= 전일) 제외 — 전일 이전 n개
    if n <= 0 or len(ys) < n:
        return None
    return max(ys[-n:])


def _lowest(xs: Sequence[Decimal], n: int) -> Decimal | None:
    ys = xs[:-1]
    if n <= 0 or len(ys) < n:
        return None
    return min(ys[-n:])


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
        RuleSpec("EXIT-1", "EXIT", _INPUTS, "CAP-TRG-01", "보유 AND 전일 종가 <= 전일 이전 exit_n거래일 최저 종가",
                 "청산 전량 시장가", "데이터 품질 실패·처리 중 주문", 1),
        RuleSpec("ENTRY-1", "ENTRY", _INPUTS, "CAP-TRG-01",
                 "보유 종목 수 < 3 AND 미보유 AND 전일 종가 > 전일 이전 entry_n거래일 최고 종가 — 돌파 강도 순으로 빈 슬롯 수만큼",
                 "진입 S-3 시장가(손절가 = 전일 이전 exit_n거래일 최저 종가)",
                 "데이터 품질 실패·거래 상태 이상·처리 중 주문·09:30 기준가 <= 손절가", 1),
    )
    params = (
        ParamSpec("entry_n", "int", "거래일", "돌파 기준 최고 종가 기간", Decimal("10"), Decimal("60")),
        ParamSpec("exit_n", "int", "거래일", "청산·손절 기준 최저 종가 기간 (< entry_n)", Decimal("5"), Decimal("40")),
        ParamSpec("risk_ratio", "decimal", "비율", "1회 위험 = 기준 금액 × 값 (L1 0.5% 이하)", Decimal("0.001"), Decimal("0.005")),
        ParamSpec("max_weight", "decimal", "비율", "종목 비중 상한 (L2 10% 이하)", Decimal("0.01"), Decimal("0.10")),
        ParamSpec("order_cap", "decimal", "원", "1회 주문 금액 상한(상한가 기준 환산, 계좌 L7 이하)", Decimal("100000"), Decimal("50000000")),
    )
    return StrategySpec(
        strategy_id=STRATEGY_ID, name="돈치언 돌파 20/10", version=VERSION,
        description="전일까지 entry_n일 최고 종가 돌파 진입, exit_n일 최저 종가 이탈 청산, 빈 슬롯은 돌파 강도 순 — 전략실 연구 후보(운영 미등록)",
        markets=("M1",), universe_method="U-A", universe=("005930",),
        capabilities=("CAP-TRG-01", "CAP-DAT-01", "CAP-ORD-01", "CAP-INS-01"),
        data_requirements="일봉 OHLC 수정주가, 워밍업 max(entry_n, exit_n)+1 거래일(종목별)",
        trigger="CAP-TRG-01 배포 설정 eval_times (1일 1회, 09:30)", rules=rules, params=params,
        signal_format="00 §2.5", validity_rule="판정 기준 시각 + 10분", validity_max_minutes=10,
        unfilled_policy="시스템 기본", sizing="S-3", holding="수일~수주, 최대 보유 제한 없음(최저 종가 이탈로 청산)",
        limits=StrategyLimits(),
    )


class DonchianBreakoutV1:
    def __init__(self) -> None:
        self.spec = build_spec()

    def evaluate(self, snapshot: EvaluationSnapshot, params: ParamValues) -> list[Signal]:
        entry_n, exit_n = int(str(params["entry_n"])), int(str(params["exit_n"]))
        if exit_n >= entry_n:
            raise ValueError("donchian-breakout: exit_n < entry_n 이어야 한다")
        warmup = max(entry_n, exit_n) + 1

        out: list[Signal] = []
        candidates: list[tuple[Decimal, str, InstrumentView, Decimal]] = []   # (돌파 강도, 코드, 뷰, 손절가)
        for v in snapshot.instruments:
            if not _ready(v, self.spec.universe) or len(v.daily_bars) < warmup:
                continue
            xs = [b.close for b in v.daily_bars]
            hi, lo = _highest(xs, entry_n), _lowest(xs, exit_n)
            if hi is None or lo is None:
                continue
            if _held(v):
                if xs[-1] <= lo:
                    out.append(_exit(self.spec, snapshot, v, "EXIT-1"))
            elif (v.position is None or v.position.quantity == 0) and xs[-1] > hi and hi > 0:
                candidates.append((xs[-1] / hi - 1, v.instrument, v, lo))

        held_total = sum(1 for v in snapshot.instruments if _held(v))
        free = TOP_N - held_total
        if free <= 0:
            return out
        for _strength, _code, v, stop in sorted(candidates, key=lambda t: (-t[0], t[1])):
            if free <= 0:
                break
            sig = _entry(self.spec, snapshot, params, v, "ENTRY-1", stop)
            if sig is not None:
                out.append(sig)
                free -= 1
        return out

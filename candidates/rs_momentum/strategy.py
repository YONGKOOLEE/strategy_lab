"""후보 rs-momentum v3 — 상대강도(횡단면 모멘텀) 상위 3종목 보유 + 청산 뒤 재진입 대기(기본 0 = 없음). 전략실 연구 후보(운영 미등록).

v1 → v2(2026-10-10): REENTRY-1 추가(개선 아님으로 결론, reentry_wait 기본값 0으로 되돌림 = v1 규칙).
v2 → v3(2026-10-11): 1회 주문 금액 상한을 상수(100만 원)에서 파라미터 `order_cap`으로 — 규모 실험용. 기본값 1,000,000이면 v1·v2와 동작 동일.
v3 → v4(2026-10-11, notes.md 사전 등록): REGIME-1 추가 — 스냅샷의 지수 종목(코드 REGIME_CODE = "KOSPI", 거래하지 않음)의
  전일 종가 <= SMA(regime_n) 이면 신규 진입 없음. 지수 종목이 스냅샷에 없거나 봉이 부족하면 **진입 없음**(보수적). 청산은 영향 없음.

규칙 (판정 1일 1회 09:30, 전일까지 확정 일봉 기준. 종목마다 신호 최대 1개, 청산 > 진입):
- 평가 가능 종목 = 유니버스 안 · 품질 통과 · 처리 중 주문 없음 · 일봉 ≥ 워밍업(max(mom_n+1, trend_n, 15)).
- 순위 = 평가 가능 종목의 mom_n 거래일 수익률 내림차순(1 = 최고, 같은 값은 종목코드 순).
- EXIT-1   : 보유 AND (순위 > exit_rank OR 종가 <= SMA(trend_n)) → 전량 시장가 청산.
- REENTRY-1: 직전 청산(사유 무관) 있음 AND 청산일(KST) 뒤 확정 일봉 수 < reentry_wait → 그 종목 진입 안 함.
- ENTRY-1  : 보유 종목 수 < TOP_N(3 = 계좌 L6) 일 때, 미보유 AND REENTRY-1 아님 AND 순위 <= TOP_N AND 수익률 > 0 AND
             종가 > SMA(trend_n) 인 종목을 순위 순으로 **빈 슬롯 수만큼만** 시장가 진입. 손절가 = 종가 − atr_mult×ATR14(크기 계산용).
  (판정 실행기는 진입 신호를 종목코드 순으로 정렬하므로, 전략이 빈 슬롯 수만 내보내 순서 편향을 없앤다. 당일 청산으로 비는 슬롯은 다음 판정에 채운다.)
순수 함수: 스냅샷과 파라미터만 본다. 파일·네트워크·현재 시각·난수를 쓰지 않는다. 지표는 tools/indicators.py에서 복사(인라인).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from trading_system.domain.clock import KST
from trading_system.domain.enums import OrderType, RequestType
from trading_system.domain.models import Signal
from trading_system.domain.sizing import round_price_down, size_fixed_amount, size_ratio, size_risk
from trading_system.domain.strategy import (
    Bar, EvaluationSnapshot, InstrumentView, ParamSpec, RuleSpec, StrategyLimits, StrategySpec)
from trading_system.strategy.base import ParamValues, make_signal

STRATEGY_ID = "rs-momentum"
VERSION = 4
TOP_N = 3                             # 보유 상한 = 계좌 L6(보유 3종목, 운영 A-034). L6이 바뀌면 버전을 올린다
REGIME_CODE = "KOSPI"                 # 국면 입력용 지수 종목 코드(data/daily/KOSPI.csv). 거래 후보에서 항상 제외
_INPUTS = ("CAP-DAT-01", "상태 입력")
_ATR_N = 14
VALID_FOR = timedelta(minutes=10)
WORST_PRICE_FACTOR = Decimal("1.3")   # 게이트는 시장가 매수 금액을 상한가(×1.3)로 평가한다
# 1회 주문 금액 상한은 파라미터 order_cap(원). 계좌 L7 이하로 설정해야 게이트 거부가 없다(운영 L7 현재 1,000,000, A-034)


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


def _pct_change(xs: Sequence[Decimal], n: int) -> Decimal | None:
    if n <= 0 or len(xs) < n + 1 or xs[-n - 1] == 0:
        return None
    return xs[-1] / xs[-n - 1] - 1


def _rank_desc(values: dict[str, Decimal]) -> dict[str, int]:
    order = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    return {k: i + 1 for i, (k, _) in enumerate(order)}


# --- 공통 도우미 (크기·신호·재진입) -----------------------------------------------------------

def _ready(v: InstrumentView, universe: tuple[str, ...]) -> bool:
    return v.instrument in universe and v.data_ok and not v.has_pending_order and bool(v.daily_bars)


def _held(v: InstrumentView) -> bool:
    return v.position is not None and v.position.owned_by_me and v.position.quantity > 0


def _reentry_blocked(v: InstrumentView, wait: int) -> bool:
    """REENTRY-1: 직전 청산일(KST) 뒤의 확정 일봉 수가 wait 미만이면 True. 스냅샷의 봉만 센다(현재 시각 없음)."""
    if wait <= 0 or v.last_exit_at is None:
        return False
    exit_day = v.last_exit_at.astimezone(KST).date()
    after = sum(1 for b in v.daily_bars if b.at > exit_day)
    return after < wait


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
                 "보유 AND (mom_n 수익률 순위 > exit_rank OR 종가 <= SMA(trend_n))",
                 "청산 전량 시장가", "데이터 품질 실패·처리 중 주문", 1),
        RuleSpec("REENTRY-1", "REENTRY_BLOCK", ("상태 입력",), "CAP-TRG-01",
                 "직전 청산 있음 AND 청산일(KST) 뒤 확정 일봉 수 < reentry_wait", "ENTRY-1 신호를 내지 않음",
                 "—", 1),
        RuleSpec("REGIME-1", "REENTRY_BLOCK", _INPUTS, "CAP-TRG-01",   # 입력 = 일봉(지수 KOSPI 종목)·상태
                 "지수(KOSPI) 전일 종가 <= SMA(regime_n) OR 지수 데이터 없음/부족", "ENTRY-1 신호를 내지 않음(청산은 영향 없음)",
                 "—", 2),
        RuleSpec("ENTRY-1", "ENTRY", _INPUTS, "CAP-TRG-01",
                 "보유 종목 수 < 3 AND 미보유 AND REENTRY-1 아님 AND REGIME-1 아님 AND 순위 <= 3 AND mom_n 수익률 > 0 AND 종가 > SMA(trend_n) "
                 "— 순위 순으로 빈 슬롯 수만큼",
                 "진입 S-3 시장가(손절가 = 종가 − atr_mult×ATR14)", "데이터 품질 실패·거래 상태 이상·처리 중 주문", 1),
    )
    params = (
        ParamSpec("mom_n", "int", "거래일", "수익률 측정 기간(약 6개월)", Decimal("60"), Decimal("250")),
        ParamSpec("trend_n", "int", "거래일", "추세 필터 이동평균 기간", Decimal("50"), Decimal("200")),
        ParamSpec("exit_rank", "int", "순위", "이 순위 밖으로 밀리면 청산(히스테리시스, > 3)", Decimal("4"), Decimal("15")),
        ParamSpec("reentry_wait", "int", "거래일", "청산 뒤 재진입 대기 확정 일봉 수 (0 = 제한 없음)", Decimal("0"), Decimal("40")),
        ParamSpec("regime_n", "int", "거래일", "국면 필터: 지수 SMA 기간 (지수 종가 <= SMA면 진입 없음, 0 = 필터 없음 = v3 규칙)", Decimal("0"), Decimal("250")),
        ParamSpec("atr_mult", "decimal", "배", "크기 계산용 손절 ATR 배수", Decimal("1"), Decimal("5")),
        ParamSpec("risk_ratio", "decimal", "비율", "1회 위험 = 기준 금액 × 값 (L1 0.5% 이하)", Decimal("0.001"), Decimal("0.005")),
        ParamSpec("max_weight", "decimal", "비율", "종목 비중 상한 (L2 10% 이하)", Decimal("0.01"), Decimal("0.10")),
        ParamSpec("order_cap", "decimal", "원", "1회 주문 금액 상한(상한가 기준 환산). 상한 = 계좌 L7 1,000,000 — 넘으면 게이트가 전부 거부하므로 ±20% 변형은 경계값으로 잘림",
                  Decimal("100000"), Decimal("1000000")),
    )
    return StrategySpec(
        strategy_id=STRATEGY_ID, name="상대강도 모멘텀 상위 3 (국면 필터)", version=VERSION,
        description="유니버스 안 mom_n 수익률 상위 3종목 보유, 순위 이탈·추세 이탈 시 청산, 청산 뒤 reentry_wait 거래일 재진입 금지(0 = 없음), "
                    "KOSPI 지수 <= SMA(regime_n)이면 신규 진입 없음, 1회 주문 상한 order_cap — 전략실 연구 후보(운영 미등록)",
        markets=("M1",), universe_method="U-A", universe=("005930",),   # 전략실 실행기는 데이터 폴더 종목으로 바꿔 실행
        capabilities=("CAP-TRG-01", "CAP-DAT-01", "CAP-ORD-01", "CAP-INS-01"),
        data_requirements="일봉 OHLC 수정주가, 워밍업 max(mom_n+1, trend_n, 15)거래일(종목별)",
        trigger="CAP-TRG-01 배포 설정 eval_times (1일 1회, 09:30)", rules=rules, params=params,
        signal_format="00 §2.5", validity_rule="판정 기준 시각 + 10분", validity_max_minutes=10,
        unfilled_policy="시스템 기본", sizing="S-3", holding="수주~수개월, 최대 보유 제한 없음(순위·추세 이탈로 청산)",
        limits=StrategyLimits(),   # 계좌 한도만. 1회 주문 상한은 파라미터 order_cap(등록 시 계좌 L7 이하 값으로)
    )


def _regime_ok(snapshot: EvaluationSnapshot, regime_n: int) -> bool:
    """REGIME-1: 지수 종목(KOSPI) 전일 종가 > SMA(regime_n)이면 True. 지수가 없거나 봉이 부족하면 False(진입 없음). regime_n 0 = 필터 없음."""
    if regime_n <= 0:
        return True
    idx = snapshot.view(REGIME_CODE)
    if idx is None or not idx.data_ok or len(idx.daily_bars) < regime_n:
        return False
    xs = [b.close for b in idx.daily_bars]
    s = _sma(xs, regime_n)
    return s is not None and xs[-1] > s


class RsMomentumV4:
    def __init__(self) -> None:
        self.spec = build_spec()

    def evaluate(self, snapshot: EvaluationSnapshot, params: ParamValues) -> list[Signal]:
        mom_n, trend_n = int(str(params["mom_n"])), int(str(params["trend_n"]))
        exit_rank, wait = int(str(params["exit_rank"])), int(str(params["reentry_wait"]))
        regime_n = int(str(params["regime_n"]))
        mult = Decimal(str(params["atr_mult"]))
        if exit_rank <= TOP_N:
            raise ValueError("rs-momentum: exit_rank > 3 이어야 한다(히스테리시스)")
        warmup = max(mom_n + 1, trend_n, _ATR_N + 1)

        # 1) 평가 가능 종목과 수익률·순위 (지수 종목은 거래 후보에서 제외)
        eligible: dict[str, InstrumentView] = {}
        moms: dict[str, Decimal] = {}
        for v in snapshot.instruments:
            if v.instrument == REGIME_CODE:
                continue
            if not _ready(v, self.spec.universe) or len(v.daily_bars) < warmup:
                continue
            m = _pct_change([b.close for b in v.daily_bars], mom_n)
            if m is None:
                continue
            eligible[v.instrument] = v
            moms[v.instrument] = m
        ranks = _rank_desc(moms)

        out: list[Signal] = []
        # 2) 청산 (보유 종목 중 평가 가능한 것)
        for code, v in eligible.items():
            if not _held(v):
                continue
            xs = [b.close for b in v.daily_bars]
            trend = _sma(xs, trend_n)
            if trend is None:
                continue
            if ranks[code] > exit_rank or xs[-1] <= trend:
                out.append(_exit(self.spec, snapshot, v, "EXIT-1"))

        # 3) 진입 — 빈 슬롯 수만큼, 순위 순. 보유 수는 전략 소유 전체(평가 불가 종목 포함)로 센다
        held_total = sum(1 for v in snapshot.instruments if _held(v) and v.instrument != REGIME_CODE)
        free = TOP_N - held_total
        if free <= 0 or not _regime_ok(snapshot, regime_n):      # REGIME-1
            return out
        for code in sorted(eligible, key=lambda c: ranks[c]):
            if free <= 0:
                break
            if ranks[code] > TOP_N:
                break
            v = eligible[code]
            if _held(v) or (v.position is not None and v.position.quantity != 0):
                continue
            if _reentry_blocked(v, wait):          # REENTRY-1
                continue
            xs = [b.close for b in v.daily_bars]
            trend, atr = _sma(xs, trend_n), _atr(v.daily_bars, _ATR_N)
            if trend is None or atr is None or moms[code] <= 0 or xs[-1] <= trend:
                continue
            stop = round_price_down(xs[-1] - mult * atr, Decimal("1"))
            sig = _entry(self.spec, snapshot, params, v, "ENTRY-1", stop)
            if sig is not None:
                out.append(sig)
                free -= 1
        return out

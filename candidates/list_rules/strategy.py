"""후보 list-rules v3 — 모드 1·2(사용자 지정 종목/목록)용 진입·청산·리스크 규칙 세트. 전략실 연구 후보(운영 미등록).

이 규칙 세트는 우위를 만들지 않는다(연구 T2). 우위는 사용자의 종목 선택이 공급하고, 시스템은 손실 제한·수익 보존·국면 회피·슬롯 준수를 한다.
규칙 (판정 1일 1회 09:30, 전일까지 확정 일봉 기준. 종목마다 신호 최대 1개, 청산 > 진입):
- REGIME-1: 지수 종목 KOSPI 전일 종가 <= SMA(regime_n) 이면 신규 진입 없음(regime_n 0 = 필터 없음, 지수 없음/부족 = 진입 없음).
- EXIT-1  : exit_mode="sma"  → 보유 AND (종가 < SMA(sma_n) OR 보유 거래일 >= hold_max) 전량 시장가 청산
            exit_mode="fixed"→ 보유 AND (종가 < 평균 매입가 × (1 − stop_pct) OR 보유 거래일 >= hold_max) 전량 시장가 청산
- REENTRY-1: 직전 청산일(KST) 뒤 확정 일봉 수 < reentry_wait 이면 진입 없음(0 = 없음).
- ENTRY-1 : 보유 종목 수 < TOP_N(3) 일 때, 미보유·REENTRY-1 아님·REGIME-1 아님 AND 전일 종가 > SMA(sma_n) 인 종목을 20일 평균 거래대금(종가×거래량) 큰 순으로
            빈 슬롯 수만큼 시장가 진입. 손절가 = 전일 종가 − atr_mult×ATR14(크기 계산용).
증액(INCREASE) 규칙 없음 — 피라미딩 연구(2026-10-11)에서 9/9년 열위.
v1 → v2(2026-10-11): ENTRY-1에 '전일 종가 > SMA(sma_n)' 추가(청산 조건 거울상 — 재진입 왕복 결함 수정).
v2 → v3(2026-10-11 19:49 사전 등록): ① 공격형 기본값 FIX12/120(파라미터 파일) ② 기간 청산을 EXIT-2로 분리(동작 동일, 사유 기록용). 이전 코드 사본 strategy-v2.py.
순수 함수: 스냅샷과 파라미터만 본다. 파일·네트워크·현재 시각·난수 없음. 지표는 tools/indicators.py에서 복사(인라인).
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

STRATEGY_ID = "list-rules"
VERSION = 3
TOP_N = 3
REGIME_CODE = "KOSPI"
_INPUTS = ("CAP-DAT-01", "상태 입력")
_ATR_N = 14
_LIQ_N = 20
VALID_FOR = timedelta(minutes=10)
WORST_PRICE_FACTOR = Decimal("1.3")


# --- 지표 (tools/indicators.py에서 복사, 수정 금지) -------------------------------------------------

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


def _avg_turnover(bars: Sequence[Bar], n: int) -> Decimal | None:
    if n <= 0 or len(bars) < n:
        return None
    return sum((b.close * b.volume for b in bars[-n:]), Decimal("0")) / n


# --- 공통 도우미 ------------------------------------------------------------------------------------

def _ready(v: InstrumentView, universe: tuple[str, ...]) -> bool:
    # U-B(사람 제출 목록): 목록 멤버십은 운영이 스냅샷 종목으로 주입한다(P-6). 전략은 spec.universe로 거르지 않는다 —
    # 거르면 운영에서 신호 0건이 조용히 지속된다(critic 2026-10-11). universe 인자는 서명 호환용.
    return v.data_ok and not v.has_pending_order and bool(v.daily_bars)


def _held(v: InstrumentView) -> bool:
    return v.position is not None and v.position.owned_by_me and v.position.quantity > 0


def _reentry_blocked(v: InstrumentView, wait: int) -> bool:
    if wait <= 0 or v.last_exit_at is None:
        return False
    exit_day = v.last_exit_at.astimezone(KST).date()
    return sum(1 for b in v.daily_bars if b.at > exit_day) < wait


def _regime_ok(snapshot: EvaluationSnapshot, regime_n: int) -> bool:
    if regime_n <= 0:
        return True
    idx = snapshot.view(REGIME_CODE)
    if idx is None or not idx.data_ok or len(idx.daily_bars) < regime_n:
        return False
    xs = [b.close for b in idx.daily_bars]
    s = _sma(xs, regime_n)
    return s is not None and xs[-1] > s


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
                 "보유 AND (exit_mode=sma: 종가 < SMA(sma_n) / exit_mode=fixed: 종가 < 평균 매입가 × (1 − stop_pct))",
                 "청산 전량 시장가", "데이터 품질 실패·처리 중 주문", 1),
        RuleSpec("EXIT-2", "EXIT", ("상태 입력",), "CAP-TRG-01", "보유 AND 보유 거래일 >= hold_max",
                 "청산 전량 시장가(기간 만료)", "데이터 품질 실패·처리 중 주문", 2),
        RuleSpec("REENTRY-1", "REENTRY_BLOCK", ("상태 입력",), "CAP-TRG-01",
                 "직전 청산 있음 AND 청산일(KST) 뒤 확정 일봉 수 < reentry_wait", "ENTRY-1 신호를 내지 않음", "—", 1),
        RuleSpec("REGIME-1", "REENTRY_BLOCK", _INPUTS, "CAP-TRG-01",
                 "지수(KOSPI) 전일 종가 <= SMA(regime_n) OR 지수 데이터 없음/부족 (regime_n 0 = 없음)", "ENTRY-1 신호를 내지 않음", "—", 2),
        RuleSpec("ENTRY-1", "ENTRY", _INPUTS, "CAP-TRG-01",
                 "보유 종목 수 < 3 AND 미보유 AND REENTRY-1·REGIME-1 아님 AND 전일 종가 > SMA(sma_n) — 20일 평균 거래대금 큰 순으로 빈 슬롯 수만큼",
                 "진입 S-3 시장가(손절가 = 전일 종가 − atr_mult×ATR14)",
                 "데이터 품질 실패·거래 상태 이상·처리 중 주문·09:30 기준가 <= 손절가", 1),
    )
    params = (
        ParamSpec("exit_mode", "str", "—", "청산 방식: sma(보수형) / fixed(공격형)", choices=("sma", "fixed")),
        ParamSpec("sma_n", "int", "거래일", "SMA 기간 — 진입 필터(종가 > SMA, 두 모드 공통)이자 보수형 청산 기준", Decimal("5"), Decimal("60")),
        ParamSpec("stop_pct", "decimal", "비율", "공격형 손절 비율(평균 매입가 대비, 종가 판정)", Decimal("0.03"), Decimal("0.20")),
        ParamSpec("hold_max", "int", "거래일", "최대 보유 거래일", Decimal("10"), Decimal("250")),
        ParamSpec("reentry_wait", "int", "거래일", "청산 뒤 재진입 대기(0 = 없음)", Decimal("0"), Decimal("40")),
        ParamSpec("regime_n", "int", "거래일", "국면 필터 지수 SMA 기간(0 = 없음)", Decimal("0"), Decimal("250")),
        ParamSpec("atr_mult", "decimal", "배", "크기 계산용 손절 ATR 배수", Decimal("1"), Decimal("5")),
        ParamSpec("risk_ratio", "decimal", "비율", "1회 위험 = 기준 금액 × 값 (L1 이하)", Decimal("0.001"), Decimal("0.005")),
        ParamSpec("max_weight", "decimal", "비율", "종목 비중 상한 (L2 이하)", Decimal("0.01"), Decimal("0.10")),
        ParamSpec("order_cap", "decimal", "원", "1회 주문 금액 상한(상한가 환산), 상한 = 계좌 L7", Decimal("100000"), Decimal("1000000")),
    )
    return StrategySpec(
        strategy_id=STRATEGY_ID, name="목록 운용 규칙 세트(즉시 진입·국면 필터·보수/공격 청산)", version=VERSION,
        description="사용자 지정 종목/목록(U-B) 안에서 국면 허용 시 거래대금 순으로 빈 슬롯만큼 진입, SMA 이탈(보수) 또는 고정 손절/기간(공격) 청산, 증액 없음 — 전략실 연구 후보(운영 미등록)",
        markets=("M1",), universe_method="U-B", universe=(), universe_list="user-list",   # 전략실 실행기는 데이터 폴더(=목록)로 바꿔 실행
        capabilities=("CAP-TRG-01", "CAP-DAT-01", "CAP-ORD-01", "CAP-INS-01"),
        data_requirements="일봉 OHLCV 수정주가, 워밍업 max(sma_n, 20, 15)거래일 + 지수 KOSPI regime_n 거래일",
        trigger="CAP-TRG-01 배포 설정 eval_times (1일 1회, 09:30)", rules=rules, params=params,
        signal_format="00 §2.5", validity_rule="판정 기준 시각 + 10분", validity_max_minutes=10,
        unfilled_policy="시스템 기본", sizing="S-3", holding="보수형 ≤120거래일 / 공격형 ≤60거래일(hold_max)",
        limits=StrategyLimits(),
    )


class ListRulesV3:
    def __init__(self) -> None:
        self.spec = build_spec()

    def evaluate(self, snapshot: EvaluationSnapshot, params: ParamValues) -> list[Signal]:
        mode = str(params["exit_mode"])
        sma_n, hold_max = int(str(params["sma_n"])), int(str(params["hold_max"]))
        stop_pct = Decimal(str(params["stop_pct"]))
        wait, regime_n = int(str(params["reentry_wait"])), int(str(params["regime_n"]))
        mult = Decimal(str(params["atr_mult"]))
        if mode not in ("sma", "fixed"):
            raise ValueError("list-rules: exit_mode는 sma 또는 fixed")
        warmup = max(sma_n, _LIQ_N, _ATR_N + 1)

        out: list[Signal] = []
        candidates: list[tuple[Decimal, str, InstrumentView, Decimal]] = []
        for v in snapshot.instruments:
            if v.instrument == REGIME_CODE or not _ready(v, self.spec.universe) or len(v.daily_bars) < warmup:
                continue
            xs = [b.close for b in v.daily_bars]
            close = xs[-1]
            if _held(v):
                assert v.position is not None
                if v.position.holding_days >= hold_max:
                    out.append(_exit(self.spec, snapshot, v, "EXIT-2")); continue
                if mode == "sma":
                    s = _sma(xs, sma_n)
                    if s is not None and close < s:
                        out.append(_exit(self.spec, snapshot, v, "EXIT-1"))
                else:
                    if close < v.position.avg_price * (1 - stop_pct):
                        out.append(_exit(self.spec, snapshot, v, "EXIT-1"))
            elif v.position is None or v.position.quantity == 0:
                if _reentry_blocked(v, wait):
                    continue
                atr, liq, s_entry = _atr(v.daily_bars, _ATR_N), _avg_turnover(v.daily_bars, _LIQ_N), _sma(xs, sma_n)
                if atr is None or liq is None or s_entry is None or close <= s_entry:   # v2: 청산 조건의 거울상
                    continue
                stop = round_price_down(close - mult * atr, Decimal("1"))
                candidates.append((liq, v.instrument, v, stop))

        held_total = sum(1 for v in snapshot.instruments if _held(v) and v.instrument != REGIME_CODE)
        free = TOP_N - held_total
        if free <= 0 or not _regime_ok(snapshot, regime_n):
            return out
        for _liq, _code, v, stop in sorted(candidates, key=lambda t: (-t[0], t[1])):
            if free <= 0:
                break
            sig = _entry(self.spec, snapshot, params, v, "ENTRY-1", stop)
            if sig is not None:
                out.append(sig)
                free -= 1
        return out

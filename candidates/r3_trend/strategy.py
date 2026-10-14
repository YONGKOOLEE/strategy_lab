"""후보 r3-trend v6 — 손익비 1:3 고정 추세추종(사용자 규칙 2026-10-11 정량화). 전략실 연구 후보(운영 미등록).

모드 2(사용자 목록) 본 용도, 모드 3(정량 스크리닝, screen="on")은 비교용. 규칙(판정 1일 1회 09:30, 전일까지 확정 일봉):
- REGIME-1 : KOSPI 전일 종가 > SMA(regime_n) AND SMA(regime_n) > 20일 전 SMA → 상승 국면. 아니면 신규 진입 없음.
- 스테이지/돌파(ENTRY-1): 최근 구간에서 ① 1stage 고점 H = high_n일 신고가 종가 ② 2stage 조정 = H 뒤 15~120거래일, 최저 종가가 H 대비
  −pull_min~−pull_max, 그 사이 H 재돌파 없음 ③ 3stage 진입 = 전일 종가 > H (첫 돌파) AND 전일 거래량 ≥ 20일 평균 × vol_mult AND
  전일 종가 > 조정 구간 매물대 상단(거래량 가중 가격 분포에서 거래량 상위 30% 구간의 상단, ATR14 폭 구간).
  screen="on"이면 추가로 상대강도(rs_n일 수익률 − KOSPI) > 0, 52주 고점 대비 ≥ −15%, ATR20/ATR120 ≤ 0.8, 20일 거래대금 중앙값 이상.
  빈 슬롯만큼 상대강도 큰 순. 손절가 = 진입 기준가 × (1 − stop_pct) (1R = stop_pct).
- 보유 관리(피크 = 보유 기간 최고 종가, 평균 매입가 기준 R):
  REDUCE-1: 피크가 처음 +1R 넘은 날 → 보유의 1/3 감액. REDUCE-2: 처음 +2R → 보유의 1/2 감액(= 초기 1/3); 1R·2R을 같은 날 처음 넘으면 2/3 감액 1건.
  EXIT-1: (v4에서 제거 — 잔량 1/3은 트레일링으로만 청산. 사용자 결정 2026-10-12: 승률보다 수익 극대화)
  EXIT-2(손절선): 종가 < 손절선 → 전량. 손절선 = 진입가 −1R; 피크 ≥ +1R 뒤 본전; 피크 ≥ +2R 뒤 max(본전, 피크 − trail_atr×ATR14).
  EXIT-3: 보유 거래일 ≥ hold_max → 전량.
- pyramid 파라미터(기본 0): v1에서는 자리만(1이면 1R 뒤 0.5단위 1회 증액 — v1 미구현, 값 1은 ValueError).
v1 → v2(2026-10-11 21:42, critic 차단 3건): EXIT-1 상태형, 1R·2R 동시 첫 돌파 시 2/3 감액, 모드 2 폐기 기준 추가(notes). 이전 코드 strategy-v1.py.
v2 → v3(2026-10-12 10:47): pyramid ParamSpec 범위 0~0 — v2 validate에서 pyramid 0→1 변형이 ValueError로 거래 0이 되어 C-4 미충족 아티팩트를 만든 것 제거. 규칙·값 변화 없음(동작 동일, 재실행 불필요). 이전 코드 strategy-v2.py.
v3 → v4(2026-10-12 사전 등록): **3R 전량 익절(EXIT-1) 제거** — 2R 감액 뒤 잔량 1/3은 피크 − trail_atr×ATR14 트레일(또는 본전·만료)로만 청산. 다른 규칙·값 불변. 이전 코드 strategy-v3.py.
v4 → v5(2026-10-12 사전 등록 research/2026-10-12-r3-v5-variants-design.md): 변형 3종을 파라미터로 — stock_sma_n(종목 추세 조건, 0=없음),
  trail_mode("r2"=2R 뒤 추적 / "entry"=진입 즉시 추적), pyramid(1이면 1R에서 REDUCE-1 대신 INCREASE 0.5×수량). 기본값이면 v4와 동작 동일. 이전 코드 strategy-v4.py.
v5 → v6(2026-10-13 13:22 사전 등록): pyramid_stop 파라미터 — 1이면 증액 뒤 손절선 하한을 **증액 가격(원래 진입가 × (1+stop_pct))**로 올린다(피크 ≥ 1R인 보유에 적용). 0이면 v5와 동일. 이전 코드 strategy-v5.py.
순수 함수. 파일·네트워크·현재 시각·난수 없음. 지표는 tools/indicators.py에서 복사(인라인).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from trading_system.domain.enums import OrderType, RequestType
from trading_system.domain.models import Signal
from trading_system.domain.sizing import round_price_down, round_qty_down, size_fixed_amount, size_ratio, size_risk
from trading_system.domain.strategy import (
    Bar, EvaluationSnapshot, InstrumentView, ParamSpec, RuleSpec, StrategyLimits, StrategySpec)
from trading_system.strategy.base import ParamValues, make_signal

STRATEGY_ID = "r3-trend"
VERSION = 6
TOP_N = 3
REGIME_CODE = "KOSPI"
_INPUTS = ("CAP-DAT-01", "상태 입력")
_ATR_N = 14
VALID_FOR = timedelta(minutes=10)
WORST_PRICE_FACTOR = Decimal("1.3")
PULL_DAYS = (15, 120)       # 2stage 조정 길이(거래일) — 사용자 규칙 정량화(제안값)
PROFILE_SHARE = Decimal("0.30")   # 매물대 = 거래량 상위 30% 구간
D1, D2, D3 = Decimal("1"), Decimal("2"), Decimal("3")


# --- 지표 (tools/indicators.py에서 복사) ---------------------------------------------------------

def _sma(xs: Sequence[Decimal], n: int) -> Decimal | None:
    if n <= 0 or len(xs) < n:
        return None
    return sum(xs[-n:], Decimal("0")) / n


def _atr_at(bars: Sequence[Bar], end: int, n: int) -> Decimal | None:
    """bars[:end+1] 기준 ATR(n)."""
    if n <= 0 or end + 1 < n + 1:
        return None
    w = bars[end - n:end + 1]
    trs = [max(b.high - b.low, abs(b.high - p.close), abs(b.low - p.close)) for p, b in zip(w[:-1], w[1:])]
    return sum(trs, Decimal("0")) / n


def _pct_change(xs: Sequence[Decimal], n: int) -> Decimal | None:
    if n <= 0 or len(xs) < n + 1 or xs[-n - 1] == 0:
        return None
    return xs[-1] / xs[-n - 1] - 1


# --- 스테이지·돌파·매물대 ------------------------------------------------------------------------

def _profile_top(bars: Sequence[Bar], start: int, end: int, width: Decimal) -> Decimal | None:
    """bars[start:end] 구간의 거래량 가중 가격 분포에서 거래량 상위 30% 구간들의 상단."""
    seg = bars[start:end]
    if not seg or width <= 0:
        return None
    lo = min(b.low for b in seg)
    bins: dict[int, Decimal] = {}
    for b in seg:
        k = int((b.close - lo) / width)
        bins[k] = bins.get(k, Decimal("0")) + b.volume
    total = sum(bins.values(), Decimal("0"))
    if total <= 0:
        return None
    acc = Decimal("0")
    top = None
    for k, vol in sorted(bins.items(), key=lambda kv: (-kv[1], kv[0])):
        acc += vol
        upper = lo + width * (k + 1)
        top = upper if top is None else max(top, upper)
        if acc >= total * PROFILE_SHARE:
            break
    return top


def _stage3_breakout(bars: Sequence[Bar], high_n: int, pull_min: Decimal, pull_max: Decimal,
                     vol_mult: Decimal) -> Decimal | None:
    """전일(bars[-1])이 3stage 첫 돌파면 H(조정 전 고점)를 돌려준다. 아니면 None."""
    c = [b.close for b in bars]
    n = len(c)
    if n < high_n + PULL_DAYS[0] + 2 or n < 22:
        return None
    last = c[-1]
    v20 = sum((b.volume for b in bars[-21:-1]), Decimal("0")) / 20
    if v20 <= 0 or bars[-1].volume < vol_mult * v20:
        return None
    for r in range(n - 1 - PULL_DAYS[0], max(high_n - 1, n - 2 - PULL_DAYS[1]) - 1, -1):
        H = c[r]
        if H != max(c[r - high_n + 1:r + 1]):
            continue                                     # 1stage 고점(high_n일 신고가)이 아님
        seg = c[r + 1:n - 1]                              # 2stage 조정(전일 제외)
        if not (PULL_DAYS[0] <= len(seg) <= PULL_DAYS[1]):
            continue
        if max(seg) > H:
            continue                                     # 조정 중 이미 돌파 → 이 H는 아님
        depth = D1 - min(seg) / H
        if not (pull_min <= depth <= pull_max):
            continue
        if last <= H:
            return None                                  # 가장 최근 유효 H를 못 넘었으면 돌파 아님
        atr = _atr_at(bars, r, _ATR_N)
        top = _profile_top(bars, r + 1, n - 1, atr) if atr else None
        if top is not None and last <= top:
            return None                                  # 매물대 상단 아래
        return H
    return None


# --- 공통 도우미 ------------------------------------------------------------------------------------

def _ready(v: InstrumentView) -> bool:
    return v.data_ok and not v.has_pending_order and bool(v.daily_bars)


def _held(v: InstrumentView) -> bool:
    return v.position is not None and v.position.owned_by_me and v.position.quantity > 0


def _regime_ok(snapshot: EvaluationSnapshot, regime_n: int) -> bool:
    if regime_n <= 0:
        return True
    idx = snapshot.view(REGIME_CODE)
    if idx is None or not idx.data_ok or len(idx.daily_bars) < regime_n + 20:
        return False
    xs = [b.close for b in idx.daily_bars]
    s_now, s_prev = _sma(xs, regime_n), _sma(xs[:-20], regime_n)
    return s_now is not None and s_prev is not None and xs[-1] > s_now and s_now > s_prev


def _index_return(snapshot: EvaluationSnapshot, n: int) -> Decimal | None:
    idx = snapshot.view(REGIME_CODE)
    if idx is None or not idx.daily_bars:
        return None
    return _pct_change([b.close for b in idx.daily_bars], n)


def _size(snapshot: EvaluationSnapshot, params: ParamValues, price: Decimal, stop: Decimal) -> Decimal:
    base = snapshot.base_amount
    by_risk = size_risk(base * Decimal(str(params["risk_ratio"])), price, stop)
    by_weight = size_ratio(base, Decimal(str(params["max_weight"])), price)
    by_cap = size_fixed_amount(Decimal(str(params["order_cap"])), price * WORST_PRICE_FACTOR)
    return min(by_risk, by_weight, by_cap)


def _price_of(v: InstrumentView) -> Decimal:
    return v.last_price if v.last_price is not None else v.daily_bars[-1].close


def _signal(spec: StrategySpec, snapshot: EvaluationSnapshot, v: InstrumentView, rule: str, kind: RequestType,
            qty: Decimal, stop: Decimal | None = None) -> Signal:
    return make_signal(spec, snapshot, v.instrument, rule, kind, qty, OrderType.MARKET, _price_of(v), VALID_FOR,
                       stop_price=stop)


# --- 명세 -----------------------------------------------------------------------------------------

def build_spec() -> StrategySpec:
    rules = (
        RuleSpec("EXIT-2", "EXIT", _INPUTS, "CAP-TRG-01",
                 "보유 AND 종가 < 손절선 [−1R; 피크 ≥ +1R면 본전; 피크 ≥ +2R면 max(본전, 피크 − trail_atr×ATR14)]",
                 "전량 시장가 청산(손절·트레일)", "데이터 품질 실패·처리 중 주문", 2),
        RuleSpec("EXIT-3", "EXIT", ("상태 입력",), "CAP-TRG-01", "보유 AND 보유 거래일 >= hold_max", "전량 시장가 청산(기간 만료)",
                 "데이터 품질 실패·처리 중 주문", 3),
        RuleSpec("REDUCE-1", "REDUCE", _INPUTS, "CAP-TRG-01", "보유 AND 피크가 처음 +1R 이상(전일)", "보유 수량의 1/3 시장가 감액",
                 "데이터 품질 실패·처리 중 주문", 1),
        RuleSpec("REDUCE-2", "REDUCE", _INPUTS, "CAP-TRG-01", "보유 AND 피크가 처음 +2R 이상(전일)", "보유 수량의 1/2 감액(초기의 1/3); 1R·2R 동시 첫 돌파면 2/3 감액",
                 "데이터 품질 실패·처리 중 주문", 2),
        RuleSpec("INCREASE-1", "INCREASE", _INPUTS, "CAP-TRG-01", "pyramid=1 AND 보유 AND 피크가 전일 처음 +1R 이상", "보유 수량의 0.5배 시장가 증액(REDUCE-1 대신)",
                 "데이터 품질 실패·처리 중 주문·거래 상태 이상", 1),
        RuleSpec("REGIME-1", "REENTRY_BLOCK", _INPUTS, "CAP-TRG-01",
                 "KOSPI 전일 종가 <= SMA(regime_n) OR SMA(regime_n) <= 20일 전 SMA OR 지수 없음 (regime_n 0 = 없음)", "ENTRY-1 신호 없음", "—", 1),
        RuleSpec("ENTRY-1", "ENTRY", _INPUTS, "CAP-TRG-01",
                 "보유 수 < 3 AND 미보유 AND REGIME-1 아님 [stock_sma_n>0: 전일 종가 > SMA(stock_sma_n)] AND 3stage 첫 돌파(high_n일 고점 H 뒤 15~120일·−pull_min~−pull_max 조정, 전일 종가 > H, "
                 "거래량 ≥ 20일 평균×vol_mult, 종가 > 매물대 상단) [screen=on: 상대강도>0·52주 고점 −15% 이내·ATR20/ATR120 ≤ 0.8·거래대금 중앙값 이상] "
                 "— 상대강도 순으로 빈 슬롯 수만큼",
                 "진입 S-3 시장가(손절가 = 기준가 × (1 − stop_pct))", "데이터 품질 실패·거래 상태 이상·처리 중 주문", 1),
    )
    params = (
        ParamSpec("stop_pct", "decimal", "비율", "1R = 손절 비율(익절 1R/2R/3R 분할)", Decimal("0.03"), Decimal("0.20")),
        ParamSpec("high_n", "int", "거래일", "1stage 고점 = high_n일 신고가 종가", Decimal("20"), Decimal("250")),
        ParamSpec("pull_min", "decimal", "비율", "2stage 조정 최소 깊이", Decimal("0.03"), Decimal("0.20")),
        ParamSpec("pull_max", "decimal", "비율", "2stage 조정 최대 깊이", Decimal("0.10"), Decimal("0.50")),
        ParamSpec("vol_mult", "decimal", "배", "돌파일 거래량 / 20일 평균", Decimal("1"), Decimal("5")),
        ParamSpec("trail_atr", "decimal", "배", "2R 뒤 트레일링 폭(ATR14 배수)", Decimal("1"), Decimal("5")),
        ParamSpec("rs_n", "int", "거래일", "상대강도 기간(우선순위·screen)", Decimal("20"), Decimal("250")),
        ParamSpec("hold_max", "int", "거래일", "최대 보유", Decimal("20"), Decimal("500")),
        ParamSpec("regime_n", "int", "거래일", "국면 SMA 기간(0 = 없음)", Decimal("0"), Decimal("250")),
        ParamSpec("screen", "str", "—", "정량 스크리닝 on/off (모드 3 비교용)", choices=("on", "off")),
        ParamSpec("pyramid", "int", "회", "불타기: 1이면 피크가 처음 1R을 넘은 날 REDUCE-1 대신 INCREASE 0.5×수량(손절선 본전)", Decimal("0"), Decimal("1")),
        ParamSpec("pyramid_stop", "int", "—", "1이면 피크 ≥ 1R(증액 뒤)부터 손절선 하한 = 원래 진입가 × (1+stop_pct); 0 = 혼합 평균가(본전)", Decimal("0"), Decimal("1")),
        ParamSpec("stock_sma_n", "int", "거래일", "종목 추세 조건 SMA 기간(0 = 없음; 150 = 바인스타인 30주선 근사)", Decimal("0"), Decimal("250")),
        ParamSpec("trail_mode", "str", "—", "r2 = 2R 뒤 추적 / entry = 진입 즉시 추적(손절선 = max(−1R·본전, 피크 − trail_atr×ATR))", choices=("r2", "entry")),
        ParamSpec("risk_ratio", "decimal", "비율", "1회 위험 = 기준 금액 × 값", Decimal("0.001"), Decimal("0.005")),
        ParamSpec("max_weight", "decimal", "비율", "종목 비중 상한", Decimal("0.01"), Decimal("0.10")),
        ParamSpec("order_cap", "decimal", "원", "1회 주문 상한(= 계좌 L7)", Decimal("100000"), Decimal("1000000")),
    )
    return StrategySpec(
        strategy_id=STRATEGY_ID, name="R3 추세추종(1:3 고정·3분할 익절·스테이지 돌파·국면)", version=VERSION,
        description="KOSPI 상승 국면에서 2stage 조정 뒤 고점 재돌파(거래량·매물대 확인) 종목에 진입, 1R/2R/3R 분할 익절·본전 이동·ATR 트레일 — 모드 2 본 용도, 모드 3 비교 — 전략실 연구 후보",
        markets=("M1",), universe_method="U-B", universe=(), universe_list="user-list",
        capabilities=("CAP-TRG-01", "CAP-DAT-01", "CAP-ORD-01", "CAP-INS-01"),
        data_requirements="일봉 OHLCV 수정주가 워밍업 max(high_n+120, 250, rs_n+1) + KOSPI regime_n+20",
        trigger="CAP-TRG-01 배포 설정 eval_times (1일 1회, 09:30)", rules=rules, params=params,
        signal_format="00 §2.5", validity_rule="판정 기준 시각 + 10분", validity_max_minutes=10,
        unfilled_policy="시스템 기본", sizing="S-3", holding="수주~hold_max(250)거래일",
        limits=StrategyLimits(),
    )


class R3TrendV6:
    def __init__(self) -> None:
        self.spec = build_spec()

    def evaluate(self, snapshot: EvaluationSnapshot, params: ParamValues) -> list[Signal]:
        stop_pct, trail = Decimal(str(params["stop_pct"])), Decimal(str(params["trail_atr"]))
        high_n, rs_n, hold_max = int(str(params["high_n"])), int(str(params["rs_n"])), int(str(params["hold_max"]))
        pull_min, pull_max = Decimal(str(params["pull_min"])), Decimal(str(params["pull_max"]))
        vol_mult, regime_n = Decimal(str(params["vol_mult"])), int(str(params["regime_n"]))
        screen = str(params["screen"]) == "on"
        pyramid = int(str(params["pyramid"])) == 1
        pyramid_stop = int(str(params["pyramid_stop"])) == 1
        stock_sma_n = int(str(params["stock_sma_n"]))
        trail_entry = str(params["trail_mode"]) == "entry"
        if pull_min >= pull_max:
            raise ValueError("r3-trend: pull_min < pull_max")
        warmup = max(high_n + PULL_DAYS[0] + 2, 250 if screen else 0, rs_n + 1, _ATR_N + 1, stock_sma_n)

        out: list[Signal] = []
        idx_ret = _index_return(snapshot, rs_n)
        cands: list[tuple[Decimal, str, InstrumentView, Decimal]] = []
        turnovers: list[Decimal] = []
        pre: list[tuple[InstrumentView, Decimal, Decimal]] = []   # (뷰, 상대강도, 거래대금)
        for v in snapshot.instruments:
            if v.instrument == REGIME_CODE or not _ready(v) or len(v.daily_bars) < warmup:
                continue
            bars = v.daily_bars
            xs = [b.close for b in bars]
            close = xs[-1]
            if _held(v):
                assert v.position is not None
                avg, hd = v.position.avg_price, v.position.holding_days
                if hd >= hold_max:
                    out.append(_signal(self.spec, snapshot, v, "EXIT-3", RequestType.EXIT, v.position.quantity)); continue
                look = max(1, min(hd, len(xs)))
                seg = xs[-look:]                              # 보유 기간 종가(진입일 포함 근사)
                peak = max(seg)
                r1, r2 = avg * (D1 + stop_pct), avg * (D1 + D2 * stop_pct)
                first_r1 = next((i for i, x in enumerate(seg) if x >= r1), None)
                first_r2 = next((i for i, x in enumerate(seg) if x >= r2), None)
                last_i = len(seg) - 1
                stop_line = avg * (D1 - stop_pct)
                if peak >= r1:
                    stop_line = avg
                    if pyramid and pyramid_stop:
                        # 원래 진입가 e 근사: 혼합 평균가 = (e + 0.5·e·(1+stop_pct)) / 1.5 → e = avg·1.5 / (1.5 + 0.5·stop_pct)
                        e0 = avg * Decimal("1.5") / (Decimal("1.5") + Decimal("0.5") * stop_pct)
                        stop_line = max(stop_line, e0 * (D1 + stop_pct))
                a = _atr_at(bars, len(bars) - 1, _ATR_N)
                if a is not None and (peak >= r2 or trail_entry):      # r2 모드: 2R 뒤 추적 / entry 모드: 진입 즉시 추적
                    stop_line = max(stop_line, peak - trail * a)
                if close < stop_line:
                    out.append(_signal(self.spec, snapshot, v, "EXIT-2", RequestType.EXIT, v.position.quantity)); continue
                if first_r2 == last_i:
                    frac = D2 / D3 if first_r1 == last_i else D1 / D2   # 1R·2R 동시 첫 돌파면 2/3, 아니면 1/2(= 초기 1/3)
                    q = round_qty_down(v.position.quantity * frac, D1)
                    if q > 0:
                        out.append(_signal(self.spec, snapshot, v, "REDUCE-2", RequestType.REDUCE, q))
                    continue
                if first_r1 == last_i:
                    if pyramid:
                        q = round_qty_down(v.position.quantity / D2, D1)
                        if q > 0 and not v.statuses:
                            out.append(_signal(self.spec, snapshot, v, "INCREASE-1", RequestType.INCREASE, q,
                                               round_price_down(avg, D1)))   # 손절가 = 본전(증액분 위험 계산용)
                    else:
                        q = round_qty_down(v.position.quantity / D3, D1)
                        if q > 0:
                            out.append(_signal(self.spec, snapshot, v, "REDUCE-1", RequestType.REDUCE, q))
                    continue
                continue
            if v.position is not None and v.position.quantity != 0:
                continue
            H = _stage3_breakout(bars, high_n, pull_min, pull_max, vol_mult)
            if H is None:
                continue
            if stock_sma_n > 0:
                s_stock = _sma(xs, stock_sma_n)
                if s_stock is None or close <= s_stock:
                    continue
            rs = _pct_change(xs, rs_n)
            if rs is None:
                continue
            rel = rs - idx_ret if idx_ret is not None else rs
            turnover = sum((b.close * b.volume for b in bars[-20:]), Decimal("0")) / 20
            pre.append((v, rel, turnover))
            turnovers.append(turnover)

        held_total = sum(1 for v in snapshot.instruments if _held(v) and v.instrument != REGIME_CODE)
        free = TOP_N - held_total
        if free <= 0 or not pre or not _regime_ok(snapshot, regime_n):
            return out
        med_turn = sorted(turnovers)[len(turnovers) // 2]
        for v, rel, turnover in pre:
            bars = v.daily_bars
            xs = [b.close for b in bars]
            close = xs[-1]
            if screen:
                if rel <= 0 or turnover < med_turn:
                    continue
                if len(xs) >= 250 and close < max(xs[-250:]) * Decimal("0.85"):
                    continue
                a20, a120 = _atr_at(bars, len(bars) - 1, 20), _atr_at(bars, len(bars) - 1, 120)
                if a20 is None or a120 is None or a120 <= 0 or a20 / a120 > Decimal("0.8"):
                    continue
            stop = round_price_down(close * (D1 - stop_pct), D1)
            cands.append((rel, v.instrument, v, stop))
        for rel, code, v, stop in sorted(cands, key=lambda t: (-t[0], t[1])):
            if free <= 0:
                break
            if v.statuses:
                continue
            price = _price_of(v)
            if stop <= 0 or stop >= price:
                continue
            qty = _size(snapshot, params, price, stop)
            if qty <= 0:
                continue
            out.append(_signal(self.spec, snapshot, v, "ENTRY-1", RequestType.ENTRY, qty, stop))
            free -= 1
        return out

"""후보 r3-trend v7 — 사용자 규칙 정정(2026-10-14) 반영: CAN SLIM식 넓은 스크리닝 + 큰 상승 뒤 조정 돌파 + 1:3 익절. 전략실 연구 후보(운영 미등록).

v1~v6은 사용자 규칙을 잘못 해석했다(+8/+16/+24% 분할 익절·1R 뒤 본전 이동). v7은 규칙 전면 교체 — 이전 결과 승계 없음. 이전 코드 strategy-v6.py.
v7 → v8(2026-10-15, 사용자 요청 "피라미딩에 따라 손절 상향 케이스"): pyr_stop 파라미터 — 증액 체결 뒤 손절선을 none(−stop_pct 유지)·half(e0×(1−stop_pct/2))·
  e0(원래 진입가 = 본전, v7 동작)·avg(증액 후 평균 단가) 중 하나로. 기본 e0이면 v7과 동작 동일. 이전 코드 strategy-v7.py.
v8 → v9(2026-10-16, 사용자 요청 "보유 종목 수 늘리기·신호 늘리기"): max_pos(전략 보유 상한, 기본 3) · align(정배열 조건 both = 일봉+주봉 /
  daily / weekly / none, 기본 both). 기본값이면 v8과 동작 동일. 이전 코드 strategy-v8.py.
v9 → v10(2026-10-16, 사용자 요청 "52주 신고가 매매" — 비교용 진입 방식 추가, 채택 아님): entry_mode(base = v9 타점 / high52 =
  전일 종가 > 직전 251일 최고 종가 H52, 단 전전일까지 fresh_n일 동안 종가가 모두 H52 미만 = 최근 fresh_n일 신고가 없던 '새 신고가',
  거래량 ≥ 50일 평균 × vol_mult(0이면 조건 없음)). high52에서는 adv/base/depth 파라미터를 쓰지 않는다. 기본 base이면 v9과 동작 동일.
  vol_mult 하한 1 → 0. 이전 코드 strategy-v9.py.
v10 → v11(2026-10-17, 사용자 매매 내역 peak 재현용 — research/2026-10-16-user-trades-analysis.md): exit_mode "sma"(1차 익절 없이
  종가 < SMA(exit_sma_n)이면 전량, 손절 −stop_pct 유지) · fresh_n 하한 0(0 = 연속 신고가도 인정). 기본값이면 v10과 동작 동일. 이전 코드 strategy-v10.py.
v11 → v12(2026-10-17): 전 종목(약 2,500) 실행용 계산량 축소 — 판정에 최근 _TAIL(300)봉만 쓴다(모든 지표 253봉 이내, 워밍업·보유 상한이
  넘으면 ValueError). 규칙·값 변화 없음(v11 결과와 바이트 동일 확인 대상). 이전 코드 strategy-v11.py.
v12 → v13(2026-10-17, 사용자 요청 "유동성 필터·진입 우선순위, 보유 종목 제한 없음"): min_turnover(20일 평균 거래대금 하한, 억 원 =
  종가×거래량 평균 / 1e8, 0 = 없음) · rank_by(빈자리 채우는 순서: rs = RS 점수 / turnover = 20일 평균 거래대금 / day_ret = 전일 상승률)
  · max_pos 상한 10 → 100. 기본값(0·rs)이면 v12와 동작 동일. 이전 코드 strategy-v12.py.
규칙(판정 1일 1회 09:30, 전일까지 확정 일봉. 아래 "전일" = bars[-1]):
- 스크리닝(모드 3, 데이터 폴더 전 종목): ① 상대강도 RS ≥ rs_min — 점수 = 2×ROC63 + ROC126 + ROC189 + ROC252(오닐식 가중 12개월),
  같은 날 점수가 있는 종목 안 백분위(낮은 점수 종목 수 / (N−1) × 100) ② 일봉 정배열: 전일 종가 > SMA20 > SMA60 > SMA120
  ③ 주봉 정배열: 주봉 종가 > 10주 SMA > 30주 SMA (주봉 = ISO 주별 마지막 종가, 진행 중인 주는 전일 종가까지).
- 매수 타점(ENTRY-1): 조정 고점 H = 직전 base_max거래일(전일 제외) 최고 종가, H 뒤 조정 길이(전일 제외) ≥ base_min,
  조정 깊이 1 − (H 뒤 최저 종가)/H 가 depth_min~depth_max, 사전 상승 H / (H 이전 adv_n거래일 최저 종가) − 1 ≥ adv_min,
  전일 종가 > H(첫 돌파 — H가 창 최고라 전전일 ≤ H 자동), 전일 거래량 ≥ 직전 50일 평균 × vol_mult.
  H는 조정 구간 고점이므로 "전고점 돌파"이고, H가 52주 고점이면 곧 "신고가 갱신"이다(둘을 따로 두지 않음).
  빈 슬롯(보유 3)만큼 RS 점수 큰 순. 손절가 = 기준가 × (1 − stop_pct). 크기 S-3: 위험 = 기준 금액 × risk_ratio(사용자: 보통 1%, 최대 2%).
- 원래 진입가 e0: 피라미딩 없으면 평균 매입가. 피라미딩 여부 = 평균가 ÷ 진입일 봉 시가(bars[-holding_days]) − 1 ≥ pyr_at/6
  → 그렇다면 e0 = 진입일 시가(체결가 근사 — 실전 09:30 체결가와 시가 차이는 한계). 증액이 거부되면 평균가가 그대로라 피라미딩 아님.
- H는 사전 상승 구간(H 이전 adv_n일)의 최고 종가 이상이어야 한다(더 높은 전고점에서 내려오는 중의 점 제외).
- 보유 관리(피크 = 보유 기간 최고 종가):
  EXIT-3 보유 거래일 ≥ hold_max → 전량.
  EXIT-2 손절선: 기본 e0 × (1 − stop_pct). 피라미딩했으면 e0(본전) — 사용자 규칙 "본전 이동은 피라미딩했을 때만".
         exit_mode = "trail"이면 진입부터, "half_trail"이면 1차 익절 뒤 max(손절선, 피크 − trail_atr × ATR14). 종가 < 손절선 → 전량.
  EXIT-4 exit_mode = "half_sma"이고 1차 익절 뒤, 또는 exit_mode = "sma"(v11, 익절 없음): 종가 < SMA(exit_sma_n) → 잔량 전량.
  TAKE-1 피크가 처음 e0 × (1 + tp_r × stop_pct) 이상(기본 3R = +24%): exit_mode "all" → 전량 EXIT, "half_*" → 보유의 1/2 REDUCE,
         "trail" → 없음(트레일만).
  INCREASE-1 pyr_at > 0이고 피크가 처음 e0 × (1 + pyr_at) 이상 → 보유 수량의 0.5배 증액 1회(손절가 = e0). TAKE-1과 같은 날이면 TAKE-1만.
- 우선순위(같은 종목 같은 날): EXIT-3 > EXIT-2 > EXIT-4 > TAKE-1 > INCREASE-1. 종목마다 신호 최대 1개.
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
VERSION = 13
_TAIL = 300            # v12: 판정에 쓰는 최근 봉 수(모든 지표가 253봉 이내 — 계산량만 줄임, 동작 동일)
REGIME_CODE = "KOSPI"
_INPUTS = ("CAP-DAT-01", "상태 입력")
_ATR_N = 14
_VOL_N = 50
_RS_LAGS = (63, 126, 189, 252)
_DMA = (20, 60, 120)          # 일봉 정배열
_WMA = (10, 30)               # 주봉 정배열
VALID_FOR = timedelta(minutes=10)
WORST_PRICE_FACTOR = Decimal("1.3")
PYR_SIZE = Decimal("0.5")
D0, D1, D2 = Decimal("0"), Decimal("1"), Decimal("2")
EXIT_MODES = ("all", "half_sma", "half_trail", "trail", "sma")
PYR_STOPS = ("none", "half", "e0", "avg")
ALIGNS = ("both", "daily", "weekly", "none")
ENTRY_MODES = ("base", "high52")
RANKS = ("rs", "turnover", "day_ret")
_H52 = 251


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


# --- 스크리닝 ---------------------------------------------------------------------------------------

def _rs_score(xs: Sequence[Decimal]) -> Decimal | None:
    """오닐식 가중 12개월: 2×ROC63 + ROC126 + ROC189 + ROC252."""
    rocs = [_pct_change(xs, n) for n in _RS_LAGS]
    if any(r is None for r in rocs):
        return None
    return D2 * rocs[0] + rocs[1] + rocs[2] + rocs[3]  # type: ignore[operator]


def _daily_aligned(xs: Sequence[Decimal]) -> bool:
    mas = [_sma(xs, n) for n in _DMA]
    if any(m is None for m in mas):
        return False
    return xs[-1] > mas[0] > mas[1] > mas[2]  # type: ignore[operator]


def _weekly_closes(bars: Sequence[Bar]) -> list[Decimal]:
    out: list[Decimal] = []
    key = None
    for b in bars:
        k = b.at.isocalendar()[:2]
        if k == key:
            out[-1] = b.close
        else:
            out.append(b.close)
            key = k
    return out


def _weekly_aligned(bars: Sequence[Bar]) -> bool:
    w = _weekly_closes(bars[-(_WMA[-1] + 5) * 5:])          # 30주 SMA에 충분한 최근 구간만(계산량)
    m10, m30 = _sma(w, _WMA[0]), _sma(w, _WMA[1])
    return m10 is not None and m30 is not None and w[-1] > m10 > m30


# --- 매수 타점 --------------------------------------------------------------------------------------

def _breakout(bars: Sequence[Bar], adv_min: Decimal, adv_n: int, base_min: int, base_max: int,
              depth_min: Decimal, depth_max: Decimal, vol_mult: Decimal) -> Decimal | None:
    """전일(bars[-1])이 큰 상승 뒤 조정 고점 H의 첫 돌파면 H, 아니면 None."""
    c = [b.close for b in bars]
    n = len(c)
    if n < base_max + adv_n + 2 or n < _VOL_N + 1:
        return None
    win = c[n - 1 - base_max:n - 1]                       # 전일 제외 직전 base_max일
    H = max(win)
    iH = n - 1 - base_max + max(i for i, x in enumerate(win) if x == H)   # 같은 값이면 가장 최근
    after = c[iH + 1:n - 1]                                # 조정 구간(전일 제외)
    if len(after) < base_min or c[-1] <= H:
        return None
    depth = D1 - min(after) / H
    if not (depth_min <= depth <= depth_max):
        return None
    prior = c[max(0, iH - adv_n):iH]
    if not prior or H < max(prior):
        return None                                        # H가 사전 상승의 고점이 아님(더 높은 전고점에서 내려오는 중) — critic 비차단 반영
    lo = min(prior + [H])
    if lo <= 0 or H / lo - D1 < adv_min:
        return None
    v_avg = sum((b.volume for b in bars[-1 - _VOL_N:-1]), Decimal("0")) / _VOL_N
    if v_avg <= 0 or bars[-1].volume < vol_mult * v_avg:
        return None
    return H


def _high52(bars: Sequence[Bar], fresh_n: int, vol_mult: Decimal) -> bool:
    """전일(bars[-1]) 종가가 직전 251일 최고 종가 H52를 넘고, 그 앞 fresh_n일(전전일까지) 종가가 모두 H52 미만인 '새 신고가'인가."""
    c = [b.close for b in bars[-(_H52 + 2):]]
    if len(c) < _H52 + 1 or fresh_n >= _H52:
        return False
    h52 = max(c[-_H52 - 1:-1])
    if c[-1] <= h52 or (fresh_n > 0 and max(c[-1 - fresh_n:-1]) >= h52):
        return False
    if vol_mult > 0:
        if len(bars) < _VOL_N + 1:
            return False
        v_avg = sum((b.volume for b in bars[-1 - _VOL_N:-1]), Decimal("0")) / _VOL_N
        if v_avg <= 0 or bars[-1].volume < vol_mult * v_avg:
            return False
    return True


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


def _first(seg: Sequence[Decimal], level: Decimal) -> int | None:
    return next((i for i, x in enumerate(seg) if x >= level), None)


# --- 명세 -----------------------------------------------------------------------------------------

def build_spec() -> StrategySpec:
    rules = (
        RuleSpec("EXIT-3", "EXIT", ("상태 입력",), "CAP-TRG-01", "보유 AND 보유 거래일 >= hold_max", "전량 시장가 청산(기간 만료)",
                 "데이터 품질 실패·처리 중 주문", 1),
        RuleSpec("EXIT-2", "EXIT", _INPUTS, "CAP-TRG-01",
                 "보유 AND 종가 < 손절선 [e0×(1−stop_pct); 피라미딩 뒤 pyr_stop(none 유지·half e0×(1−stop_pct/2)·e0 본전·avg 평균 단가); trail: 진입부터 / half_trail: 1차 익절 뒤 max(손절선, 피크 − trail_atr×ATR14)]",
                 "전량 시장가 청산(손절·트레일)", "데이터 품질 실패·처리 중 주문", 2),
        RuleSpec("EXIT-4", "EXIT", _INPUTS, "CAP-TRG-01", "(exit_mode=half_sma AND 1차 익절 뒤) OR exit_mode=sma — 종가 < SMA(exit_sma_n)",
                 "잔량 전량 시장가 청산", "데이터 품질 실패·처리 중 주문", 3),
        RuleSpec("TAKE-1", "EXIT", _INPUTS, "CAP-TRG-01", "보유 AND 피크가 전일 처음 e0×(1+tp_r×stop_pct) 이상 AND exit_mode=all",
                 "전량 시장가 익절", "데이터 품질 실패·처리 중 주문", 4),
        RuleSpec("TAKE-1H", "REDUCE", _INPUTS, "CAP-TRG-01", "보유 AND 피크가 전일 처음 e0×(1+tp_r×stop_pct) 이상 AND exit_mode=half_sma|half_trail",
                 "보유 수량의 1/2 시장가 감액", "데이터 품질 실패·처리 중 주문", 4),
        RuleSpec("INCREASE-1", "INCREASE", _INPUTS, "CAP-TRG-01", "pyr_at>0 AND 보유 AND 피크가 전일 처음 e0×(1+pyr_at) 이상 AND TAKE 아님",
                 "보유 수량의 0.5배 시장가 증액 1회(손절가 = pyr_stop에 따른 증액 뒤 손절선)", "데이터 품질 실패·처리 중 주문·거래 상태 이상", 5),
        RuleSpec("REGIME-1", "REENTRY_BLOCK", _INPUTS, "CAP-TRG-01",
                 "KOSPI 전일 종가 <= SMA(regime_n) OR SMA(regime_n) <= 20일 전 SMA OR 지수 없음 (regime_n 0 = 없음)", "ENTRY-1 신호 없음", "—", 1),
        RuleSpec("ENTRY-1", "ENTRY", _INPUTS, "CAP-TRG-01",
                 "[entry_mode=high52: 전일 종가 > 직전 251일 최고 종가 AND 그 전 fresh_n일 종가 모두 그 미만 AND 거래량 ≥ 50일 평균×vol_mult — 아래 조정 돌파 조건 대신] 보유 수 < max_pos AND 미보유 AND REGIME-1 아님 AND RS 백분위 ≥ rs_min AND [align: both = 일봉 종가>SMA20>SMA60>SMA120 AND 주봉 종가>10주>30주 / daily / weekly / none] "
                 "AND 조정 고점 H(직전 base_max일 최고 종가) 뒤 base_min일 이상·깊이 depth_min~depth_max 조정 AND H/(H 이전 adv_n일 최저) − 1 ≥ adv_min "
                 "AND 전일 종가 > H AND 전일 거래량 ≥ 50일 평균×vol_mult — RS 점수 순으로 빈 슬롯 수만큼",
                 "진입 S-3 시장가(손절가 = 기준가 × (1 − stop_pct))", "데이터 품질 실패·거래 상태 이상·처리 중 주문", 1),
    )
    params = (
        ParamSpec("stop_pct", "decimal", "비율", "1R = 손절 비율(사용자 −8%)", Decimal("0.03"), Decimal("0.20")),
        ParamSpec("tp_r", "decimal", "R", "1차 익절 = tp_r × stop_pct 상승(사용자 1:3 → 3 = +24%)", Decimal("1"), Decimal("10")),
        ParamSpec("exit_mode", "str", "—", "all = 1차 익절 전량 / half_sma = 1/2 뒤 SMA 이탈 / half_trail = 1/2 뒤 ATR 트레일 / trail = 익절 없이 진입부터 트레일 / sma = 익절 없이 SMA 이탈 전량",
                  choices=EXIT_MODES),
        ParamSpec("exit_sma_n", "int", "거래일", "half_sma 잔량 청산 SMA 기간", Decimal("10"), Decimal("200")),
        ParamSpec("trail_atr", "decimal", "배", "트레일 폭(ATR14 배수)", Decimal("1"), Decimal("6")),
        ParamSpec("pyr_at", "decimal", "비율", "피라미딩 트리거 상승률(0 = 없음). 증액 0.5배 1회, 손절선은 pyr_stop", Decimal("0"), Decimal("0.20")),
        ParamSpec("pyr_stop", "str", "—", "증액 뒤 손절선: none = e0×(1−stop_pct) 유지 / half = e0×(1−stop_pct/2) / e0 = 본전(원래 진입가) / avg = 증액 후 평균 단가",
                  choices=PYR_STOPS),
        ParamSpec("adv_min", "decimal", "비율", "조정 전 사전 상승률(사용자 +50%)", Decimal("0.10"), Decimal("2")),
        ParamSpec("adv_n", "int", "거래일", "사전 상승 측정 구간(H 이전)", Decimal("20"), Decimal("250")),
        ParamSpec("base_min", "int", "거래일", "조정 최소 길이", Decimal("5"), Decimal("120")),
        ParamSpec("base_max", "int", "거래일", "조정 고점 탐색 구간(최대 조정 길이)", Decimal("10"), Decimal("250")),
        ParamSpec("depth_min", "decimal", "비율", "조정 최소 깊이", Decimal("0"), Decimal("0.30")),
        ParamSpec("depth_max", "decimal", "비율", "조정 최대 깊이", Decimal("0.05"), Decimal("0.60")),
        ParamSpec("vol_mult", "decimal", "배", "돌파일 거래량 / 50일 평균(0 = 조건 없음)", Decimal("0"), Decimal("5")),
        ParamSpec("rs_min", "decimal", "백분위", "상대강도 백분위 하한(사용자 70)", Decimal("0"), Decimal("99")),
        ParamSpec("hold_max", "int", "거래일", "최대 보유", Decimal("20"), Decimal("500")),
        ParamSpec("max_pos", "int", "종목", "전략 보유 종목 상한(계좌 L6 이하로 운영)", Decimal("1"), Decimal("100")),
        ParamSpec("min_turnover", "decimal", "억 원", "20일 평균 거래대금(종가×거래량) 하한, 0 = 없음", Decimal("0"), Decimal("10000")),
        ParamSpec("rank_by", "str", "—", "빈자리 채우는 순서: rs / turnover(20일 평균 거래대금) / day_ret(전일 상승률)", choices=RANKS),
        ParamSpec("align", "str", "—", "정배열 조건: both = 일봉+주봉 / daily / weekly / none", choices=ALIGNS),
        ParamSpec("entry_mode", "str", "—", "진입 방식: base = 큰 상승 뒤 조정 돌파(v9) / high52 = 새 52주 신고가", choices=ENTRY_MODES),
        ParamSpec("fresh_n", "int", "거래일", "high52: 돌파 전 신고가가 없어야 하는 기간(0 = 연속 신고가도 인정)", Decimal("0"), Decimal("120")),
        ParamSpec("regime_n", "int", "거래일", "국면 SMA 기간(0 = 없음 — 국면은 배분 규칙 담당)", Decimal("0"), Decimal("250")),
        ParamSpec("risk_ratio", "decimal", "비율", "1회 위험 = 기준 금액 × 값(사용자 보통 1%, 최대 2%)", Decimal("0.001"), Decimal("0.02")),
        ParamSpec("max_weight", "decimal", "비율", "종목 비중 상한", Decimal("0.01"), Decimal("0.30")),
        ParamSpec("order_cap", "decimal", "원", "1회 주문 상한", Decimal("100000"), Decimal("100000000")),
    )
    return StrategySpec(
        strategy_id=STRATEGY_ID, name="R3 추세추종 v7(CAN SLIM식 스크리닝·큰 상승 뒤 조정 돌파·1:3 익절)", version=VERSION,
        description="RS 백분위·일/주봉 정배열로 넓게 거른 종목 중 큰 상승 뒤 조정 고점을 거래량과 함께 돌파하면 진입, −8% 손절·+24% 1차 익절·피라미딩 시 본전 손절 — 전략실 연구 후보",
        markets=("M1",), universe_method="U-A", universe=("005930",),   # 전략실 실행기는 데이터 폴더 종목으로 바꿔 실행
        capabilities=("CAP-TRG-01", "CAP-DAT-01", "CAP-ORD-01", "CAP-INS-01"),
        data_requirements="일봉 OHLCV 수정주가 워밍업 max(253, base_max+adv_n+2, 주봉 30주) (+ regime_n>0이면 KOSPI regime_n+20)",
        trigger="CAP-TRG-01 배포 설정 eval_times (1일 1회, 09:30)", rules=rules, params=params,
        signal_format="00 §2.5", validity_rule="판정 기준 시각 + 10분", validity_max_minutes=10,
        unfilled_policy="시스템 기본", sizing="S-3", holding="수주~hold_max(250)거래일",
        limits=StrategyLimits(),
    )


class R3TrendV13:
    def __init__(self) -> None:
        self.spec = build_spec()

    def evaluate(self, snapshot: EvaluationSnapshot, params: ParamValues) -> list[Signal]:
        dec = lambda k: Decimal(str(params[k]))  # noqa: E731
        num = lambda k: int(str(params[k]))      # noqa: E731
        stop_pct, tp_r, trail, pyr_at = dec("stop_pct"), dec("tp_r"), dec("trail_atr"), dec("pyr_at")
        pyr_stop = str(params["pyr_stop"])
        if pyr_stop not in PYR_STOPS:
            raise ValueError(f"r3-trend: pyr_stop {pyr_stop}")
        exit_mode, exit_sma_n, hold_max = str(params["exit_mode"]), num("exit_sma_n"), num("hold_max")
        adv_min, adv_n, base_min, base_max = dec("adv_min"), num("adv_n"), num("base_min"), num("base_max")
        depth_min, depth_max, vol_mult, rs_min = dec("depth_min"), dec("depth_max"), dec("vol_mult"), dec("rs_min")
        regime_n, max_pos, align = num("regime_n"), num("max_pos"), str(params["align"])
        entry_mode, fresh_n = str(params["entry_mode"]), num("fresh_n")
        min_turnover, rank_by = dec("min_turnover"), str(params["rank_by"])
        if rank_by not in RANKS:
            raise ValueError(f"r3-trend: rank_by {rank_by}")
        if entry_mode not in ENTRY_MODES:
            raise ValueError(f"r3-trend: entry_mode {entry_mode}")
        if align not in ALIGNS:
            raise ValueError(f"r3-trend: align {align}")
        if exit_mode not in EXIT_MODES:
            raise ValueError(f"r3-trend: exit_mode {exit_mode}")
        if depth_min >= depth_max or base_min >= base_max:
            raise ValueError("r3-trend: depth_min < depth_max, base_min < base_max")
        if pyr_at >= tp_r * stop_pct and pyr_at > 0:
            raise ValueError("r3-trend: pyr_at < 1차 익절")
        warmup = max(_RS_LAGS[-1] + 1, base_max + adv_n + 2, _DMA[-1], _VOL_N + 1, exit_sma_n)
        if warmup > _TAIL or hold_max + 2 > _TAIL:
            raise ValueError(f"r3-trend: 워밍업 {warmup}·보유 상한 {hold_max}이 최근 봉 {_TAIL}개를 넘음")

        out: list[Signal] = []
        scores: dict[str, Decimal] = {}
        views: list[InstrumentView] = []
        for v in snapshot.instruments:
            if v.instrument == REGIME_CODE or not _ready(v) or len(v.daily_bars) < warmup:
                continue
            views.append(v)
            s = _rs_score([b.close for b in v.daily_bars[-_TAIL:]])
            if s is not None:
                scores[v.instrument] = s
        ranked = sorted(scores.values())

        def rs_pct(code: str) -> Decimal | None:
            s = scores.get(code)
            if s is None or len(ranked) < 2:
                return None
            below = sum(1 for x in ranked if x < s)
            return Decimal(below) * 100 / (len(ranked) - 1)

        cands: list[tuple[Decimal, str, InstrumentView]] = []
        for v in views:
            bars = v.daily_bars[-_TAIL:]
            xs = [b.close for b in bars]
            close = xs[-1]
            if _held(v):
                assert v.position is not None
                sig = self._manage(snapshot, v, xs, bars, stop_pct, tp_r, trail, pyr_at, exit_mode, exit_sma_n, hold_max, pyr_stop)
                if sig is not None:
                    out.append(sig)
                continue
            if v.position is not None and v.position.quantity != 0:
                continue
            p = rs_pct(v.instrument)
            if p is None or p < rs_min:
                continue
            if entry_mode == "high52":
                if not _high52(bars, fresh_n, vol_mult):
                    continue
            elif _breakout(bars, adv_min, adv_n, base_min, base_max, depth_min, depth_max, vol_mult) is None:
                continue                                       # 싼 조건부터(결과 동일, 계산량만 줄임)
            if (align in ("both", "daily") and not _daily_aligned(xs)) or (align in ("both", "weekly") and not _weekly_aligned(bars)):
                continue
            turnover = sum((b.close * b.volume for b in bars[-20:]), Decimal("0")) / 20 / Decimal("100000000")
            if min_turnover > 0 and turnover < min_turnover:
                continue
            key = (scores[v.instrument] if rank_by == "rs" else turnover if rank_by == "turnover"
                   else (xs[-1] / xs[-2] - D1 if len(xs) >= 2 and xs[-2] > 0 else Decimal("-1")))
            cands.append((key, v.instrument, v))

        held_total = sum(1 for v in snapshot.instruments if _held(v) and v.instrument != REGIME_CODE)
        free = max_pos - held_total
        if free <= 0 or not cands or not _regime_ok(snapshot, regime_n):
            return out
        for _, code, v in sorted(cands, key=lambda t: (-t[0], t[1])):
            if free <= 0:
                break
            if v.statuses:
                continue
            price = _price_of(v)
            stop = round_price_down(price * (D1 - stop_pct), D1)
            if stop <= 0 or stop >= price:
                continue
            qty = _size(snapshot, params, price, stop)
            if qty <= 0:
                continue
            out.append(_signal(self.spec, snapshot, v, "ENTRY-1", RequestType.ENTRY, qty, stop))
            free -= 1
        return out

    def _manage(self, snapshot: EvaluationSnapshot, v: InstrumentView, xs: list[Decimal], bars: Sequence[Bar],
                stop_pct: Decimal, tp_r: Decimal, trail: Decimal, pyr_at: Decimal, exit_mode: str, exit_sma_n: int,
                hold_max: int, pyr_stop: str = "e0") -> Signal | None:
        pos = v.position
        assert pos is not None
        avg, hd, qty = pos.avg_price, pos.holding_days, pos.quantity
        if hd >= hold_max:
            return _signal(self.spec, snapshot, v, "EXIT-3", RequestType.EXIT, qty)
        seg = xs[-max(1, min(hd, len(xs))):]                 # 보유 기간 종가(진입일 포함 근사)
        last_i, peak, close = len(seg) - 1, max(seg), xs[-1]
        # 원래 진입가 e0와 피라미딩 여부(critic 2026-10-14 차단 1 수정): holding_days는 진입 다음 거래일부터 세므로(진입일 0)
        # bars[-hd] = 진입일 봉, 그 시가 ≈ 진입 체결가(백테스트 기준가 = 당일 시가). 평균가가 그보다 pyr_at/6 이상 높으면 증액 체결로 본다
        # (예상 상승 = 0.5·pyr_at/1.5 = pyr_at/3의 절반). 증액 거부·미체결이면 평균가 불변 → 피라미딩 아님(본전 이동 없음)으로 바르게 처리.
        pyramided, e0 = False, avg
        if pyr_at > 0 and 1 <= hd <= len(bars):
            e_open = bars[-hd].open
            if e_open > 0 and avg / e_open - D1 >= pyr_at / 6:
                pyramided, e0 = True, e_open
        tp_level = e0 * (D1 + tp_r * stop_pct)
        i_tp = _first(seg, tp_level)
        took = i_tp is not None and i_tp < last_i and exit_mode in ("half_sma", "half_trail")
        stop_line = e0 * (D1 - stop_pct)
        if pyramided:                                        # v8: 증액 뒤 손절선 선택(none이면 그대로)
            stop_line = {"none": stop_line, "half": e0 * (D1 - stop_pct / D2), "e0": e0, "avg": avg}[pyr_stop]
        a = _atr_at(bars, len(bars) - 1, _ATR_N)
        if a is not None and (exit_mode == "trail" or (exit_mode == "half_trail" and took)):
            stop_line = max(stop_line, peak - trail * a)
        if close < stop_line:
            return _signal(self.spec, snapshot, v, "EXIT-2", RequestType.EXIT, qty)
        if (took and exit_mode == "half_sma") or exit_mode == "sma":
            s = _sma(xs, exit_sma_n)
            if s is not None and close < s:
                return _signal(self.spec, snapshot, v, "EXIT-4", RequestType.EXIT, qty)
        if i_tp == last_i and exit_mode not in ("trail", "sma"):
            if exit_mode == "all":
                return _signal(self.spec, snapshot, v, "TAKE-1", RequestType.EXIT, qty)
            q = round_qty_down(qty / D2, D1)
            return _signal(self.spec, snapshot, v, "TAKE-1H", RequestType.REDUCE, q) if q > 0 else None
        if pyr_at > 0 and not pyramided and _first(seg, e0 * (D1 + pyr_at)) == last_i and not v.statuses:
            q = round_qty_down(qty * PYR_SIZE, D1)
            if q > 0:
                new_avg = (avg * qty + _price_of(v) * q) / (qty + q)
                stop_after = {"none": e0 * (D1 - stop_pct), "half": e0 * (D1 - stop_pct / D2), "e0": e0, "avg": new_avg}[pyr_stop]
                return _signal(self.spec, snapshot, v, "INCREASE-1", RequestType.INCREASE, q,
                               round_price_down(stop_after, D1))   # 손절가 = 증액 뒤 손절선(게이트 위험 계산용)
        return None

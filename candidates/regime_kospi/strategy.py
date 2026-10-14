"""배분 규칙 regime-kospi v1 — KOSPI 지수 국면으로 지정 전략의 신규 진입을 허용/불허 (운영 CP-034 D-199, kind=ALLOCATION). 전략실 연구 후보.

규칙(ALLOC-1): 지수 마지막 확정 종가 > SMA(sma_days) AND SMA(sma_days) > slope_days일 전 SMA → 지정 전략 신규 진입 허용. 아니면 불허(청산·감액은 영향 없음).
전략실 rs-momentum v4·r3-trend·list-rules의 내장 REGIME-1(스냅샷 종목 KOSPI 사용)과 같은 조건을 **운영 배분 규칙 인터페이스**로 옮긴 것.
입력은 IndexView(bars = 판정일 이전 확정 지수 일봉)뿐. 지수 결측·품질 실패(data_ok False)면 불허(운영이 알림).
"""

from __future__ import annotations

from decimal import Decimal

from trading_system.domain.allocation import AllocationDecision, IndexView
from trading_system.domain.strategy import ParamSpec, RuleSpec, StrategyLimits, StrategySpec

RULE_ID = "regime-kospi"
VERSION = 1
TARGETS = ("rs-momentum", "r3-trend", "list-rules")   # 지정 전략 ID(전략실 후보). 운영 등록 시 배포 대상에 맞춰 조정


def build_spec() -> StrategySpec:
    return StrategySpec(
        strategy_id=RULE_ID, name="KOSPI 국면 배분 규칙(SMA + 기울기)", version=VERSION,
        description="KOSPI 종가 > SMA(sma_days) AND SMA 상승(slope_days일 전 대비)이면 지정 전략 신규 진입 허용 — 전략실 연구 후보(운영 미등록)",
        markets=("M1",), universe_method="U-A", universe=(), kind="ALLOCATION", allocation_targets=TARGETS,
        capabilities=("CAP-TRG-01", "CAP-DAT-05d"),
        data_requirements="지수 일봉(CAP-DAT-05d, ka20006 001) sma_days + slope_days 개, 전 거래일까지 확정값",
        trigger="CAP-TRG-01 지정 전략 판정 직전",
        rules=(RuleSpec("ALLOC-1", "ALLOCATION", ("CAP-DAT-05d",), "CAP-TRG-01",
                        "지수 종가 > SMA(sma_days) AND SMA(sma_days) > slope_days일 전 SMA", "지정 전략 신규 진입 허용",
                        "지수 결측·지연·품질 실패 → 불허", 1),),
        params=(ParamSpec("sma_days", "int", "거래일", "지수 단순 이동평균 기간", Decimal("20"), Decimal("300")),
                ParamSpec("slope_days", "int", "거래일", "SMA 기울기 비교 간격(0 = 기울기 조건 없음)", Decimal("0"), Decimal("60"))),
        signal_format="배분 결정(허용 여부)", validity_rule="해당 없음", validity_max_minutes=1,
        unfilled_policy="시스템 기본", sizing="해당 없음", holding="해당 없음", limits=StrategyLimits(),
    )


class RegimeKospiV1:
    index_code = "001"

    def __init__(self) -> None:
        self.spec = build_spec()

    def decide(self, index: IndexView, params: dict) -> AllocationDecision:
        n, k = int(str(params["sma_days"])), int(str(params["slope_days"]))
        if not index.data_ok:
            return AllocationDecision(False, f"지수 데이터 없음/품질 실패: {index.issue}")
        if len(index.bars) < n + k:
            return AllocationDecision(False, f"지수 일봉 {len(index.bars)}개 < {n + k}")
        closes = [b.close for b in index.bars]
        sma = sum(closes[-n:], Decimal("0")) / n
        last = closes[-1]
        above = last > sma
        rising = True
        sma_prev = None
        if k > 0:
            sma_prev = sum(closes[-n - k:-k], Decimal("0")) / n
            rising = sma > sma_prev
        allow = above and rising
        reason = ("종가 > SMA" if above else "종가 <= SMA") + ("" if k == 0 else (" & SMA 상승" if rising else " & SMA 하락/횡보"))
        ev = {"close": str(last), "sma": str(sma)}
        if sma_prev is not None:
            ev["sma_prev"] = str(sma_prev)
        return AllocationDecision(allow, reason, ev)

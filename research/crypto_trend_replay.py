"""crypto-trend strategy.py 대조 — 운영 도메인 객체로 1시간마다 스냅샷을 만들어 evaluate를 부르는 간이 재생(운영 엔진 아님). 판정 아님.

목적: candidates/crypto_trend/strategy.py가 전략실 1시간 모형(research/btc_intraday_study.py v1(hourly, gate=True))과 같은 매매를 내는지.
재생 규칙: 매 1시간 봉 종가에 판정(last_price = 그 봉 종가, daily_bars = 그날 전까지 확정 UTC 일봉 최근 60개, base_amount = 현금 + 보유 × 종가),
신호는 다음 봉 시가 × (1 ± 슬리피지 0.05%) 체결, 수수료 0.1%, 한 계좌 공유 현금(매수가 현금을 넘으면 현금 한도로 줄임).
  python research/crypto_trend_replay.py BTCUSDT            → 1종목·params(위험 5%·상한 98%) — 시뮬레이터 A-h와 대조
  python research/crypto_trend_replay.py BTCUSDT ETHUSDT    → 2종목·params-v2(위험 2.5%·상한 49%, period_minutes는 evaluate에 영향 없음)
"""

from __future__ import annotations

import sys
import tomllib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(r"C:\AI\trading_system\trading_system") / "src"))
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "research"))
from trading_system.domain.enums import RequestType  # noqa: E402
from trading_system.domain.strategy import Bar, EvaluationSnapshot, InstrumentView, PositionView  # noqa: E402

from btc_monitor_study import load_hours  # noqa: E402
from candidates.crypto_trend.strategy import CryptoTrendV2  # noqa: E402

FEE, SLIP = Decimal("0.001"), Decimal("0.0005")
D = Decimal


def base_params(n_syms: int) -> dict:
    params = tomllib.loads((LAB / "candidates" / "crypto_trend" / "params-v2.toml").read_text(encoding="utf-8"))["params"]
    return dict(params, risk_ratio="0.05", max_weight="0.98") if n_syms == 1 else params


_HOURS: dict = {}


def replay(syms: list[str], params: dict, start: date = date(2017, 9, 1), end: date = date(2025, 12, 31), slip: Decimal = Decimal("0.0005"),
           skip_hours: frozenset = frozenset()) -> dict:
    """재생 1회. 반환: 청산 거래 손익 목록(USDT, 비용 반영)·최종 자산·MDD."""
    strat = CryptoTrendV2()
    for s in syms:
        if s not in _HOURS:
            _HOURS[s] = {h[0]: h for h in load_hours(LAB / "data" / "crypto" / f"{s}-1h.csv")}
    hours = {s: _HOURS[s] for s in syms}
    times = sorted(set.intersection(*[set(h) for h in hours.values()]))
    daily: dict[str, list[Bar]] = {s: [] for s in syms}
    cur: dict[str, list] = {s: [] for s in syms}
    cash = D(10000)
    pos = {s: [D(0), D(0)] for s in syms}           # 수량, 평균가
    pend: dict[str, tuple] = {}
    trades, peak, mdd = [], D(0), D(0)
    cost: dict[str, Decimal] = {}
    pnls: list[Decimal] = []
    rel: list[float] = []                            # 거래 손익 ÷ 진입 직전 자산(재표본용)
    eq = cash
    last_day = None
    for t in times:
        d = t.date()
        if d != last_day:                              # 날이 바뀌면 전날 일봉 확정
            for s in syms:
                if cur[s]:
                    o, hi, lo, c = cur[s][0][1], max(x[2] for x in cur[s]), min(x[3] for x in cur[s]), cur[s][-1][4]
                    daily[s].append(Bar(last_day, D(str(o)), D(str(hi)), D(str(lo)), D(str(c)), D(0)))
                cur[s] = []
            last_day = d
        for s in syms:
            cur[s].append(hours[s][t])
        if d < start or d > end:
            continue
        for s, (kind, q) in list(pend.items()):        # 시가 체결 — 매도 먼저
            if kind == "sell" and pos[s][0] > 0:
                px = D(str(hours[s][t][1])) * (1 - slip)
                cash += pos[s][0] * px * (1 - FEE)
                c0, e0 = cost.pop(s)
                pnls.append(pos[s][0] * px * (1 - FEE) - c0)
                rel.append(float(pnls[-1] / e0))
                trades.append((s, "sell", t))
                pos[s] = [D(0), D(0)]
        for s, (kind, q) in list(pend.items()):
            if kind == "buy" and pos[s][0] == 0:
                px = D(str(hours[s][t][1])) * (1 + slip)
                q = min(q, cash / (px * (1 + FEE)))
                q = (q / D("0.00001")).to_integral_value(rounding="ROUND_FLOOR") * D("0.00001")
                if q > 0:
                    cash -= q * px * (1 + FEE)
                    cost[s] = (q * px * (1 + FEE), eq)
                    pos[s] = [q, px]
                    trades.append((s, "buy", t))
        pend = {}
        closes = {s: D(str(hours[s][t][4])) for s in syms}
        eq = cash + sum(pos[s][0] * closes[s] for s in syms)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
        views = tuple(InstrumentView(instrument=s, daily_bars=tuple(daily[s][-60:]), last_price=closes[s],
                                     position=PositionView(pos[s][0], pos[s][1], 0, True) if pos[s][0] > 0 else None) for s in syms)
        asof = datetime(t.year, t.month, t.day, t.hour, tzinfo=timezone.utc) + timedelta(hours=1)
        snap = EvaluationSnapshot(evaluation_id=f"r-{t:%Y%m%d%H}", market="M2", account="REPLAY", as_of=asof, base_amount=eq, instruments=views)
        if asof.hour in skip_hours:                  # Q: 운영 60분 일정은 01:00~23:00(00:00 판정 없음)
            continue
        for sig in strat.evaluate(snap, params):
            pend[sig.instrument] = ("sell", None) if sig.kind == RequestType.EXIT else ("buy", sig.quantity)
    return {"pnls": pnls, "rel": rel, "final": eq, "mdd": mdd, "trades": trades}


def main(syms: list[str]) -> int:
    r = replay(syms, base_params(len(syms)))
    trades, eq, mdd = r["trades"], r["final"], r["mdd"]
    n = sum(1 for x in trades if x[1] == "sell")
    print(f"재생 {syms} · 청산 거래 {n} · 최종 {eq:,.0f} ({eq / 10000 - 1:+.1%}) · MDD {mdd:.1%} · 종목별 청산 " +
          str({s: sum(1 for x in trades if x[0] == s and x[1] == 'sell') for s in syms}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["BTCUSDT"]))

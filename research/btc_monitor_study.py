"""BTC — 일봉 경계(UTC 시각) 민감도와 1시간 간격 '24시간 감시' 근사 (판정 아님).

사용자 질문(2026-10-17): 코인은 종가 개념이 없으니 24시간 감시가 가능한가, 아니면 바이낸스 일봉(UTC 00:00) 경계를 따라야 하나.
- (A) 경계 민감도: 1시간 봉으로 하루 시작 시각을 UTC 0~23시로 바꾼 일봉 24가지를 만들어 같은 규칙을 돌린다. 결과가 고르면 경계와 무관한 추세 효과.
- (B) 1시간 감시: 1시간 봉에서 매시간 판단 — 돌파 = 현재 1시간 종가 > 직전 N×24시간 종가 최고, 청산 = 1시간 종가 < 직전 n×24시간 종가 평균,
  손절 = 매입가 × (1 − stop_pct)(1시간 저가 기준 장중), 체결 = 다음 1시간 봉 시가. cryptosim.simulate를 1시간 봉에 그대로 쓴다(기간 ×24).
입력: data/crypto/BTCUSDT-1h.csv(운영 1분봉에서 묶은 사본, 2025-12-31까지). 출력: 표준출력.
"""

from __future__ import annotations

import csv
import statistics as st
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import cryptosim as cs  # noqa: E402

RULES = [  # (이름, entry_n일, exit_n일)
    ("20일 돌파·50일선", 20, 50), ("20일 돌파·40일선", 20, 40), ("20일 돌파·60일선", 20, 60),
    ("30일 돌파·50일선", 30, 50), ("55일 돌파·50일선", 55, 50), ("10일 돌파·50일선", 10, 50),
]
START, END = date(2017, 9, 1), date(2025, 12, 31)


def load_hours(p: Path) -> list[tuple[datetime, float, float, float, float, float]]:
    out = []
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append((datetime.fromisoformat(r["time"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])))
    return out


def daily_with_offset(hours: list, off: int) -> list[tuple[date, float, float, float, float, float]]:
    """하루 = [날짜 off시, 다음 날 off시). 라벨 = 시작 날짜."""
    days: dict[date, list] = {}
    for t, o, h, l, c, v in hours:
        d = (t - timedelta(hours=off)).date()
        b = days.get(d)
        if b is None:
            days[d] = [o, h, l, c, v]
        else:
            b[1] = max(b[1], h); b[2] = min(b[2], l); b[3] = c; b[4] += v
    return [(d, *b) for d, b in sorted(days.items())]


def params(entry_n: int, exit_n: int, scale: int = 1) -> dict:
    return dict(cs.DEFAULTS, risk_ratio=1.0, max_weight=1.0, entry_n=entry_n * scale, exit_n=exit_n * scale, regime_n=0,
                stop_mode="pct", stop_pct=0.08, stop_when="intraday", exit_mode="sma")


def main() -> int:
    hours = load_hours(LAB / "data" / "crypto" / "BTCUSDT-1h.csv")
    print(f"1시간 봉 {len(hours)}개 · 기간 {START}~{END} · 100% 투자·수수료 0.1%·슬리피지 0.05% · 판정 아님")
    print("\n(A) 일봉 시작 시각(UTC)별 — 각 규칙의 24가지 결과 분포")
    dailies = {off: daily_with_offset(hours, off) for off in range(24)}
    for name, en, ex in RULES:
        res = []
        for off, rows in dailies.items():
            r = cs.simulate(rows, params(en, ex), START, END)
            res.append((off, r["ret"], r["mdd"], r["trades"]))
        rets = sorted(x[1] for x in res); mdds = sorted(x[2] for x in res)
        bh = cs.simulate(dailies[0], params(en, ex), START, END)
        u0 = next(x for x in res if x[0] == 0)
        print(f"  {name}: 수익 최소 {rets[0]:+.0%} · 중앙 {st.median(rets):+.0%} · 최대 {rets[-1]:+.0%} | MDD 최소 {mdds[0]:.0%} 중앙 {st.median(mdds):.0%} 최대 {mdds[-1]:.0%}"
              f" | UTC 00시(바이낸스) {u0[1]:+.0%}·{u0[2]:.0%} | 그냥 보유 {bh['buy_hold_ret']:+.0%}·{bh['buy_hold_mdd']:.0%}")
    print("\n(B) 1시간마다 판단(24시간 감시 근사) — 기간을 시간으로 환산(×24), 다음 1시간 시가 체결")
    st_dt, en_dt = datetime.combine(START, datetime.min.time()), datetime.combine(END, datetime.max.time())
    for name, en, ex in RULES:
        r = cs.simulate(hours, params(en, ex, 24), st_dt, en_dt)
        yr = r["year_ret"]
        print(f"  {name}: 수익 {r['ret']:+.0%} MDD {r['mdd']:.0%} 거래 {r['trades']} 승률 {r['win_rate']:.0%} "
              f"(2018 {yr.get('2018', 0):+.0%}, 2022 {yr.get('2022', 0):+.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

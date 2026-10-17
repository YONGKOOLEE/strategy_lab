"""② btc-trend v1 규칙을 다른 자산(코스피·코스닥 지수 — ETF 대용 가정)에 그대로 적용. 판정 아님.

사전 등록: research/2026-10-18-btc-preverdict-design.md ② (2026-10-18 00:19). 도구 cryptosim(다음 봉 시가 체결).
규칙 v1 그대로: 25일 종가 돌파·50일선 청산·손절 매입가 − 2×ATR14(종가 판정)·위험 5%·최대 비중 98%.
비용: 수수료 0.015%·슬리피지 0.1%·매도세 없음(ETF 가정). 비율 = 연 수익(CAGR)/MDD.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import cryptosim as cs  # noqa: E402

ASSETS = {"코스피": LAB / "data" / "index" / "001.csv", "코스닥": LAB / "data" / "krall-index" / "101.csv"}
PERIODS = {"앞 2016-03~2020": (date(2016, 3, 1), date(2020, 12, 31)), "뒤 2021~2025": (date(2021, 1, 1), date(2025, 12, 31)),
           "전체": (date(2016, 3, 1), date(2025, 12, 31))}
V1 = dict(entry_rule="breakout", entry_n=25, exit_mode="sma", exit_n=50, stop_mode="atr", stop_atr=2.0, stop_when="close",
          risk_ratio=0.05, max_weight=0.98, fee=0.00015, slip=0.001)


def ratio(ret: float, mdd: float, s: date, e: date) -> float:
    cagr = (1 + ret) ** (365.25 / ((e - s).days + 1)) - 1
    return cagr / mdd if mdd > 0 else float("inf")


def main() -> int:
    out, verdicts = {}, {}
    print("v1 규칙을 지수에 적용(ETF 대용 가정) — 판정 아님 · 수익·MDD·비율(연 수익/MDD) | 그냥 보유")
    for name, path in ASSETS.items():
        rows = cs.load_csv(path)
        out[name] = {}
        wins = []
        for per, (s, e) in PERIODS.items():
            r = cs.simulate(rows, dict(cs.DEFAULTS, **V1), s, e)
            rt, rb = ratio(r["ret"], r["mdd"], s, e), ratio(r["buy_hold_ret"], r["buy_hold_mdd"], s, e)
            out[name][per] = {"ret": r["ret"], "mdd": r["mdd"], "ratio": rt, "trades": r["trades"], "win": r["win_rate"],
                              "avg": r["avg_ret"], "bh_ret": r["buy_hold_ret"], "bh_mdd": r["buy_hold_mdd"], "bh_ratio": rb}
            if per != "전체":
                wins.append(rt > rb)
            print(f"  {name} {per:16s} 추세 {r['ret']:+7.1%}·{r['mdd']:5.1%}·{rt:5.2f} 거래 {r['trades']:2d} 승률 {r['win_rate']:.0%} 거래당 {r['avg_ret']:+.2%}"
                  f" | 보유 {r['buy_hold_ret']:+7.1%}·{r['buy_hold_mdd']:5.1%}·{rb:5.2f}")
        verdicts[name] = "both" if all(wins) else "none" if not any(wins) else "mixed"
    v = list(verdicts.values())
    concl = ("다른 자산에서도 추세 효과 — BTC 결과 지지" if all(x == "both" for x in v)
             else "BTC 고유 가능성 — 한계 문장 강화" if all(x == "none" for x in v) else "불분명")
    print(f"\n사전 기준 결과: {verdicts} → {concl}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-cross-asset.json"
    f.write_text(json.dumps({"table": out, "verdicts": verdicts, "conclusion": concl}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {f.relative_to(LAB)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

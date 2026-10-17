"""BTC 다른 전략 계열 비교 (판정 아님) — 사전 등록 research/2026-10-17-crypto-design.md "추가 등록 — 다른 전략 계열 비교"(23:17).

계열: 추세 후보 btc-trend v1(위험 5% / 98% 고정), S1 단순 기준(SMA 보유 n, 시계열 모멘텀 L), S2 역추세(RSI(2) 눌림 매수), S3 묶기(50:50 독립 계좌).
기간: 학습 2017-09-01~2021-12-31(고르는 데만 씀), 확인 2022-01-01~2025-12-31(고르지 않음), 전체 2017-09-01~2025-12-31.
일봉 경계 UTC 0~23시 24가지(1시간 봉에서 생성)의 중앙값 + UTC 00시(바이낸스) 값. 비용 수수료 0.1%·슬리피지 0.05%, 다음 봉 시가 체결.
지표: 수익, MDD, 연 수익(CAGR)/MDD 비율, 거래 수. 선택 기준(S1·S2 상위) = 학습 구간 24경계 중앙 CAGR/MDD.
출력: 표준출력 + results/cryptosim/<날짜>-alt-study.json
"""

from __future__ import annotations

import json
import statistics as st
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
sys.path.insert(0, str(LAB / "research"))
import cryptosim as cs  # noqa: E402
from btc_monitor_study import daily_with_offset, load_hours  # noqa: E402

PERIODS = {"학습": (date(2017, 9, 1), date(2021, 12, 31)), "확인": (date(2022, 1, 1), date(2025, 12, 31)),
           "전체": (date(2017, 9, 1), date(2025, 12, 31))}
TREND = dict(entry_rule="breakout", entry_n=25, exit_mode="sma", exit_n=50, stop_mode="atr", stop_atr=2.0, stop_when="close")


def cfgs() -> dict[str, dict]:
    out = {"T 추세 위험5%": dict(TREND, risk_ratio=0.05, max_weight=0.98),
           "T 추세 98%": dict(TREND, risk_ratio=1.0, max_weight=0.98)}
    for n in (100, 150, 200):
        out[f"S1 SMA{n} 보유"] = dict(entry_rule="above_sma", entry_n=n, exit_mode="sma", exit_n=n, stop_mode="none", max_weight=0.98)
    for L in (90, 180, 365):
        out[f"S1 모멘텀{L}"] = dict(entry_rule="tsmom", entry_n=L, exit_mode="tsmom", exit_n=L, stop_mode="none", max_weight=0.98)
    for r in (5, 10, 20):
        for f in (0, 200):
            for h in (5, 10):
                for sz, rr in (("위험5%", 0.05), ("98%", 1.0)):
                    out[f"S2 RSI<{r} {'SMA200위' if f else '필터없음'} {h}일 {sz}"] = dict(
                        entry_rule="rsi2", rsi_th=float(r), entry_n=2, regime_n=f, exit_mode="mr", exit_n=5, hold_max=h,
                        stop_mode="pct", stop_pct=0.08, stop_when="intraday", risk_ratio=rr, max_weight=0.98)
    return out


def metrics(curve: list[tuple[str, float]], cash: float, start: date, end: date) -> tuple[float, float, float]:
    peak, mdd = 0.0, 0.0
    for _, v in curve:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    ret = curve[-1][1] / cash - 1
    cagr = (1 + ret) ** (365.25 / ((end - start).days + 1)) - 1
    return ret, mdd, cagr / mdd if mdd > 0 else float("inf")


def run(rows: list, kw: dict, per: str, cash: float = 10000.0) -> dict:
    s, e = PERIODS[per]
    return cs.simulate(rows, dict(cs.DEFAULTS, cash=cash, **kw), s, e)


def combine(a: list, b: list) -> list:
    assert [d for d, _ in a] == [d for d, _ in b]
    return [(d, x + y) for (d, x), (_, y) in zip(a, b)]


def corr(xs: list[float], ys: list[float]) -> float:
    mx, my = st.fmean(xs), st.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else float("nan")


def daily_rets(curve: list) -> list[float]:
    return [b[1] / a[1] - 1 for a, b in zip(curve, curve[1:])]


def main() -> int:
    hours = load_hours(LAB / "data" / "crypto" / "BTCUSDT-1h.csv")
    dailies = {off: daily_with_offset(hours, off) for off in range(24)}
    C = cfgs()
    table: dict[str, dict] = {}
    for name, kw in C.items():
        table[name] = {}
        for per, (s, e) in PERIODS.items():
            rs = [run(dailies[off], kw, per) for off in range(24)]
            m = [metrics(r["eq_curve"], 10000.0, s, e) for r in rs]
            table[name][per] = {"ret_med": st.median(x[0] for x in m), "mdd_med": st.median(x[1] for x in m),
                                "ratio_med": st.median(x[2] for x in m), "ret_min": min(x[0] for x in m),
                                "trades_med": st.median(r["trades"] for r in rs), "ret_u0": m[0][0], "mdd_u0": m[0][1],
                                "bh_ret": rs[0]["buy_hold_ret"], "bh_mdd": rs[0]["buy_hold_mdd"],
                                "win_u0": rs[0]["win_rate"], "avg_u0": rs[0]["avg_ret"]}
    pick = lambda pre: max((n for n in C if n.startswith(pre)), key=lambda n: table[n]["학습"]["ratio_med"])  # noqa: E731
    s1, s2 = pick("S1"), pick("S2")
    combos = {f"S3 추세5%+{s2}": (C["T 추세 위험5%"], C[s2]), f"S3 추세5%+{s1}": (C["T 추세 위험5%"], C[s1])}
    for name, (ka, kb) in combos.items():
        table[name] = {}
        for per, (s, e) in PERIODS.items():
            m = []
            for off in range(24):
                ca = run(dailies[off], ka, per, 5000.0)["eq_curve"]
                cb = run(dailies[off], kb, per, 5000.0)["eq_curve"]
                m.append(metrics(combine(ca, cb), 10000.0, s, e))
            table[name][per] = {"ret_med": st.median(x[0] for x in m), "mdd_med": st.median(x[1] for x in m),
                                "ratio_med": st.median(x[2] for x in m), "ret_min": min(x[0] for x in m),
                                "ret_u0": m[0][0], "mdd_u0": m[0][1]}
    # 추세와의 상관(UTC 00시, 전체): 일별 자산 변화율, 연도별 수익
    ct = run(dailies[0], C["T 추세 위험5%"], "전체")
    cors = {}
    for n in (s1, s2):
        r = run(dailies[0], C[n], "전체")
        yt, yo = ct["year_ret"], r["year_ret"]
        ys = sorted(set(yt) & set(yo))
        cors[n] = {"daily": corr(daily_rets(ct["eq_curve"]), daily_rets(r["eq_curve"])),
                   "yearly": corr([yt[y] for y in ys], [yo[y] for y in ys]), "years": {y: (yt[y], yo[y]) for y in ys}}

    bh = table["T 추세 위험5%"]
    print("BTC 다른 전략 계열 비교 — 24개 일봉 경계 중앙값(UTC00 값) · 비율 = 연 수익/MDD · 판정 아님, 생존편향·사후 선택 자산(과대 추정)")
    print(f"그냥 보유(UTC00): 학습 {bh['학습']['bh_ret']:+.0%}·MDD {bh['학습']['bh_mdd']:.0%} | 확인 {bh['확인']['bh_ret']:+.0%}·{bh['확인']['bh_mdd']:.0%} | 전체 {bh['전체']['bh_ret']:+.0%}·{bh['전체']['bh_mdd']:.0%}")
    hdr = "  ".join(f"{p}: 수익 MDD 비율" for p in PERIODS)
    print(f"{'설정':34s} {hdr}  거래(전체)")
    for name, t in table.items():
        cells = "  ".join(f"{t[p]['ret_med']:+8.0%} {t[p]['mdd_med']:4.0%} {t[p]['ratio_med']:4.2f}" for p in PERIODS)
        tr = t["전체"].get("trades_med", "")
        print(f"{name:34s} {cells}  {tr}")
    print(f"\n학습 구간으로 고른 상위: S1 = {s1}, S2 = {s2}")
    for n, cr in cors.items():
        print(f"추세(위험5%)와 상관 — {n}: 일별 {cr['daily']:+.2f}, 연도별 {cr['yearly']:+.2f}  "
              + " ".join(f"{y}:{a:+.0%}/{b:+.0%}" for y, (a, b) in cr["years"].items()))
    out = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-alt-study.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"table": table, "pick": {"S1": s1, "S2": s2}, "corr": cors}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n저장: {out.relative_to(LAB)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

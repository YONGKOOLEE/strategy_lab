"""CC. 다종목 연간 갱신판 — 연도 Y 목록 = Y−1년 거래대금 상위 N(그 당시, 상장폐지 포함), btc-trend v1 일봉 한 계좌. 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md CC (2026-10-18 08:06). 데이터: data/crypto/universe(운영 A-118 사본).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
sys.path.insert(0, str(LAB / "research"))
import cryptosim as cs  # noqa: E402
from crypto_universe_study import LEVER, STABLE, base_asset, with_delist  # noqa: E402

UNI = LAB / "data" / "crypto" / "universe"
START, END = date(2019, 1, 1), date(2025, 12, 31)
FEE, SLIP = 0.001, 0.0005


def load_all() -> dict[str, list]:
    out = {}
    for f in sorted(UNI.glob("*USDT-1d.csv")):
        sym = f.name.split("-")[0]
        b = base_asset(sym)
        if b in STABLE or LEVER.search(b):
            continue
        rows = [r for r in cs.load_csv(f) if r[0] <= END]
        if rows:
            out[sym] = rows
    return out


def qv_by_year(folder: Path, syms: list[str]) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    for s in syms:
        for r in cs.csv.DictReader((folder / f"{s}-1d.csv").open(encoding="utf-8")):
            y = int(r["date"][:4])
            out.setdefault(y, {}).setdefault(s, 0.0)
            out[y][s] += float(r.get("quote_volume") or 0)
    return out


def lists_for(n: int, data: dict[str, list], qv: dict) -> dict[int, list[str]]:
    lists = {}
    for y in range(START.year, END.year + 1):
        prev_end = date(y - 1, 12, 25)
        alive = [s for s, rows in data.items() if rows[-1][0] >= prev_end and rows[0][0] <= date(y - 1, 12, 31)]
        lists[y] = sorted(alive, key=lambda s: -qv.get(y - 1, {}).get(s, 0.0))[:n]
    return lists


def simulate(data: dict[str, list], lists: dict[int, list[str]], n: int, start: date = START, end: date = END, entry_n: int = 25,
             exit_n: int = 50, stop_atr: float = 2.0, risk_tot: float = 0.05, cap_tot: float = 0.98, slip: float = SLIP) -> dict:
    """한 계좌 — 그해 목록 종목만 신규 진입, 보유는 청산 신호까지. 폐지 = with_delist 가짜 봉(× 0.9)에서 강제 청산."""
    use = sorted({s for l in lists.values() for s in l})
    rows_l = {s: with_delist(data[s])[0] for s in use}
    rows = {s: {r[0]: r for r in rw} for s, rw in rows_l.items()}
    idx = {s: {r[0]: k for k, r in enumerate(rw)} for s, rw in rows_l.items()}
    cl = {s: [r[4] for r in rw] for s, rw in rows_l.items()}
    atr = {s: cs.atr_series(rw) for s, rw in rows_l.items()}
    last_day = {s: rw[-1][0] for s, rw in rows_l.items()}
    dates = sorted({d for rw in rows_l.values() for d in (r[0] for r in rw) if start <= d <= end})
    risk, cap = risk_tot / n, cap_tot / n
    cost: dict[str, float] = {}
    pnls: list[float] = []
    cash = 10000.0
    pos = {s: {"qty": 0.0, "stop": 0.0, "pend": None} for s in use}
    curve, exits = [], 0
    for d in dates:
        live = [s for s in use if d in rows[s]]
        eq_open = cash + sum(pos[s]["qty"] * rows[s][d][1] for s in live)
        for s in live:
            p = pos[s]
            if p["qty"] > 0 and (p["pend"] == "sell" or d == last_day[s]):
                px = (rows[s][d][1] if p["pend"] == "sell" else rows[s][d][4]) * (1 - slip)
                cash += p["qty"] * px * (1 - FEE)
                pnls.append(p["qty"] * px * (1 - FEE) - cost.pop(s))
                p["qty"], p["pend"] = 0.0, None
                exits += 1
        for s in live:
            p = pos[s]
            if isinstance(p["pend"], tuple) and p["qty"] == 0 and d != last_day[s]:
                px = rows[s][d][1] * (1 + slip)
                sl = px - stop_atr * p["pend"][1]
                dist = (px - sl) / px
                w = min(cap, risk / dist) if dist > 0 else 0.0
                q = min(eq_open * w, cash) / (px * (1 + FEE))
                if q * px >= 5 and sl > 0:
                    cash -= q * px * (1 + FEE)
                    cost[s] = q * px * (1 + FEE)
                    p["qty"], p["stop"] = q, sl
            if isinstance(p["pend"], tuple):
                p["pend"] = None
        listed = set(lists[d.year])
        for s in live:
            p, k, c = pos[s], idx[s][d], cl[s]
            if d == last_day[s]:
                continue
            if p["qty"] > 0:
                if c[k] < p["stop"] or (k + 1 >= exit_n and c[k] < sum(c[k - exit_n + 1:k + 1]) / exit_n):
                    p["pend"] = "sell"
            elif s in listed and k >= entry_n and c[k] > max(c[k - entry_n:k]) and atr[s][k] is not None:
                p["pend"] = ("buy", atr[s][k])
        curve.append(cash + sum(pos[s]["qty"] * rows[s][d][4] for s in live))
    return metrics(curve, start, end) | {"exits": exits, "pnls": pnls}


def basket(data: dict[str, list], lists: dict[int, list[str]]) -> dict:
    """그해 목록 같은 금액 그냥 보유, 연초 재조정(매매 비용 반영), 폐지 시 마지막 종가 × 0.9로 현금화."""
    v = 10000.0
    curve = []
    for y in range(START.year, END.year + 1):
        syms = lists[y]
        part = v / len(syms)
        hold = {}
        for s in syms:
            rw = [r for r in with_delist(data[s])[0] if r[0].year == y and r[0] >= START]
            if rw:
                hold[s] = (part / (rw[0][1] * (1 + SLIP) * (1 + FEE)), {r[0]: r[4] for r in rw}, rw[-1][4])
        days = sorted({d for _, m, _ in hold.values() for d in m})
        for d in days:
            curve.append(sum(q * m.get(d, last if d > max(m) else next(iter(m.values()))) for q, m, last in hold.values()) +
                         part * (len(syms) - len(hold)))
        v = curve[-1] * (1 - FEE) if curve else v
    return metrics(curve, START, END)


def metrics(curve: list[float], start: date, end: date) -> dict:
    peak = mdd = 0.0
    for x in curve:
        peak = max(peak, x)
        mdd = max(mdd, (peak - x) / peak)
    ret = curve[-1] / 10000 - 1
    cagr = (1 + ret) ** (365.25 / ((end - start).days + 1)) - 1 if ret > -1 else -1.0
    return {"ret": ret, "mdd": mdd, "ratio": cagr / mdd if mdd else float("inf")}


def main() -> int:
    data = load_all()
    qv = qv_by_year(UNI, list(data))
    yrs = END.year - START.year + 1
    fixed = {y: ["BTCUSDT", "ETHUSDT"] for y in range(START.year, END.year + 1)}
    fx = simulate(data, fixed, 2)
    print(f"CC. 다종목 연간 갱신판(btc-trend v1 일봉 한 계좌, 2019~2025) · 판정 아님 — 비교 고정 BTC+ETH: {fx['ret']:+.0%}·MDD {fx['mdd']:.1%}·비율 {fx['ratio']:.2f}·청산 {fx['exits']}(연 {fx['exits']/yrs:.1f})")
    out = {"fixed2": fx}
    verdicts = []
    for n in (5, 10):
        lists = lists_for(n, data, qv)
        r = simulate(data, lists, n)
        b = basket(data, lists)
        out[n] = {"lists": lists, "res": r, "basket": b}
        print(f"  N={n}: {r['ret']:+.0%}·MDD {r['mdd']:.1%}·비율 {r['ratio']:.2f}·청산 {r['exits']}(연 {r['exits']/yrs:.1f}) | 목록 보유(연초 재조정) {b['ret']:+.0%}·MDD {b['mdd']:.1%}·비율 {b['ratio']:.2f}")
        print("    목록: " + " / ".join(f"{y}: {','.join(base_asset(s) for s in l)}" for y, l in lists.items()))
        if r["ratio"] > fx["ratio"] and r["exits"] / yrs >= 15:
            verdicts.append(f"N={n} 다종목 연간 갱신판 v3 후보(가설)")
        elif r["exits"] / yrs >= 15 and r["ratio"] > b["ratio"]:
            verdicts.append(f"N={n} 거래 수 대안(성과 희생)")
    print("사전 기준: " + ("; ".join(verdicts) if verdicts else "2종목 유지"))
    (LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-annual-universe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

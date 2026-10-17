"""Z. 상장폐지 포함 코인 목록(2018 거래대금 상위 20)으로 btc-trend v1 생존편향 점검. 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md Z (2026-10-18 02:22, 데이터 요청 전).

  python research/crypto_universe_study.py <일봉 폴더>    (폴더: 전략실 사본 data/crypto/universe — date,open,high,low,close,volume,quote_volume)
  python research/crypto_universe_study.py --check        (도구 확인: BTC·ETH만 — 기존 결과와 같아야 함)
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import cryptosim as cs  # noqa: E402
cs.TICK = 1e-8   # 2026-10-18 첫 실행 뒤 수정: cryptosim 기본 호가 0.01 USDT가 저가 코인(TRX·VET 등)에서 체결가를 크게 왜곡 → 사실상 단위 없음(바이낸스 실제 단위는 심볼별, 미반영)

V1 = dict(entry_rule="breakout", entry_n=25, exit_mode="sma", exit_n=50, stop_mode="atr", stop_atr=2.0, stop_when="close",
          risk_ratio=0.05, max_weight=0.98)
STABLE = {"USDC", "TUSD", "PAX", "USDP", "BUSD", "USDS", "FDUSD", "DAI", "USDSB", "EUR", "GBP", "AUD", "SUSD", "UST", "USTC", "TRY"}
LEVER = re.compile(r"(UP|DOWN|BULL|BEAR)$")
START, END = date(2019, 1, 1), date(2025, 12, 31)
HAIRCUT = 0.9
FEE, SLIP, TICK = 0.001, 0.0005, 0.01


def base_asset(sym: str) -> str:
    return sym[:-4] if sym.endswith("USDT") else sym


def pick_top20(folder: Path) -> list[tuple[str, float]]:
    vols = []
    for f in sorted(folder.glob("*USDT-1d.csv")):
        sym = f.name.split("-")[0]
        b = base_asset(sym)
        if b in STABLE or LEVER.search(b):
            continue
        tot = 0.0
        for r in cs.csv.DictReader(f.open(encoding="utf-8")):
            if "2018-01-01" <= r["date"] <= "2018-12-31":
                tot += float(r.get("quote_volume") or 0)
        if tot > 0:
            vols.append((sym, tot))
    vols.sort(key=lambda x: -x[1])
    return vols[:20]


def with_delist(rows: list) -> tuple[list, bool]:
    """마지막 봉이 END보다 이르면 상장폐지로 보고 다음 날 가짜 봉(종가 × 0.9) 1개를 붙인다(Z 보수 가정)."""
    last = rows[-1]
    if last[0] >= END - timedelta(days=3):
        return rows, False
    px = last[4] * HAIRCUT
    return rows + [(last[0] + timedelta(days=1), px, px, px, px, 0.0)], True


def ratio(ret: float, mdd: float, s: date, e: date) -> float:
    if mdd <= 0:
        return float("inf")
    yrs = max((e - s).days, 1) / 365.25
    cagr = (1 + ret) ** (1 / yrs) - 1 if ret > -1 else -1.0
    return cagr / mdd


def per_coin(rows: list) -> dict:
    rows, delisted = with_delist(rows)
    s = max(START, rows[0][0])
    e = min(END, rows[-1][0])
    r = cs.simulate(rows, dict(cs.DEFAULTS, **V1), s, e)
    pnl = [q * (x * (1 - FEE) - en * (1 + FEE)) for _, _, en, x, q, _ in r["trade_list"]]
    return {"start": str(s), "end": str(e), "delisted": delisted, "ret": r["ret"], "mdd": r["mdd"], "ratio": ratio(r["ret"], r["mdd"], s, e),
            "bh_ret": r["buy_hold_ret"], "bh_mdd": r["buy_hold_mdd"], "bh_ratio": ratio(r["buy_hold_ret"], r["buy_hold_mdd"], s, e),
            "trades": r["trades"], "ev": sum(pnl) / len(pnl) if pnl else 0.0}


def portfolio(data: dict[str, list]) -> dict:
    """한 계좌 N종목(종목별 위험 5%/N·상한 98%/N), 날짜 합집합 — 데이터 없는 종목은 건너뜀, 폐지 가짜 봉에서 강제 청산."""
    n = len(data)
    risk, cap = 0.05 / n, 0.98 / n
    rows = {s: {r[0]: r for r in rw} for s, rw in data.items()}
    idx = {s: {r[0]: k for k, r in enumerate(rw)} for s, rw in data.items()}
    cl = {s: [r[4] for r in rw] for s, rw in data.items()}
    atr = {s: cs.atr_series(rw) for s, rw in data.items()}
    last_day = {s: rw[-1][0] for s, rw in data.items()}
    dates = sorted({d for rw in data.values() for d in (r[0] for r in rw) if START <= d <= END})
    cash = 10000.0
    pos = {s: {"qty": 0.0, "stop": 0.0, "pend": None} for s in data}
    curve, trades = [], 0
    bh_q = {}
    for d in dates:
        live = [s for s in data if d in rows[s]]
        eq_open = cash + sum(pos[s]["qty"] * rows[s][d][1] for s in live) + sum(pos[s]["qty"] * cl[s][-1] for s in data if s not in live and pos[s]["qty"] > 0)
        for s in live:
            p = pos[s]
            if (p["pend"] == "sell" or d == last_day[s]) and p["qty"] > 0:
                px = rows[s][d][1] if p["pend"] == "sell" else rows[s][d][4]
                px = px * (1 - SLIP)
                cash += p["qty"] * px * (1 - FEE)
                p["qty"], p["pend"] = 0.0, None
                trades += 1
        for s in live:
            p = pos[s]
            if isinstance(p["pend"], tuple) and p["qty"] == 0 and d != last_day[s]:
                px = rows[s][d][1] * (1 + SLIP)
                sl = px - 2.0 * p["pend"][1]
                dist = (px - sl) / px
                w = min(cap, risk / dist) if dist > 0 else 0.0
                q = min(eq_open * w, cash) / (px * (1 + FEE))
                if q * px >= 5 and sl > 0:
                    cash -= q * px * (1 + FEE)
                    p["qty"], p["stop"] = q, sl
            if isinstance(p["pend"], tuple):
                p["pend"] = None
        for s in live:
            p, k, c = pos[s], idx[s][d], cl[s]
            if d == last_day[s]:
                continue
            if p["qty"] > 0:
                if c[k] < p["stop"] or (k + 1 >= 50 and c[k] < sum(c[k - 49:k + 1]) / 50):
                    p["pend"] = "sell"
            elif k >= 25 and c[k] > max(c[k - 25:k]) and atr[s][k] is not None:
                p["pend"] = ("buy", atr[s][k])
            if s not in bh_q:
                bh_q[s] = (10000 / n) / (rows[s][d][1] * (1 + SLIP) * (1 + FEE))
        eq = cash + sum(pos[s]["qty"] * (rows[s][d][4] if s in live else cl[s][-1]) for s in data)
        bh = sum(q * (rows[s][d][4] if d in rows[s] else cl[s][-1]) for s, q in bh_q.items()) + (10000 / n) * (n - len(bh_q))
        curve.append((d, eq, bh))
    def mdd_of(xs: list[float]) -> float:
        peak = m = 0.0
        for v in xs:
            peak = max(peak, v)
            m = max(m, (peak - v) / peak)
        return m
    eqs, bhs = [c[1] for c in curve], [c[2] for c in curve]
    r1, r2 = eqs[-1] / 10000 - 1, bhs[-1] / 10000 - 1
    m1, m2 = mdd_of(eqs), mdd_of(bhs)
    return {"ret": r1, "mdd": m1, "ratio": ratio(r1, m1, START, END), "bh_ret": r2, "bh_mdd": m2, "bh_ratio": ratio(r2, m2, START, END), "exits": trades}


def load_dir(folder: Path, syms: list[str]) -> dict[str, list]:
    out = {}
    for s in syms:
        rows = cs.load_csv(folder / f"{s}-1d.csv")
        rows = [r for r in rows if r[0] <= END]
        out[s] = with_delist(rows)[0] if rows else rows
    return {s: r for s, r in out.items() if r}


def main(argv: list[str]) -> int:
    if argv == ["--check"]:
        folder = LAB / "data" / "crypto"
        for s in ("BTCUSDT", "ETHUSDT"):
            x = per_coin([r for r in cs.load_csv(folder / f"{s}-1d.csv") if r[0] <= END])
            print(f"  도구 확인 {s} 2019~2025: v1 {x['ret']:+.0%}·MDD {x['mdd']:.1%}·비율 {x['ratio']:.2f}·거래 {x['trades']} | 보유 {x['bh_ret']:+.0%}·{x['bh_ratio']:.2f}")
        p = portfolio(load_dir(folder, ["BTCUSDT", "ETHUSDT"]))
        print(f"  묶음 확인(BTC·ETH, 종목별 위험 2.5%): {p['ret']:+.0%}·MDD {p['mdd']:.1%}·비율 {p['ratio']:.2f} | 보유 {p['bh_ret']:+.0%}·{p['bh_ratio']:.2f}")
        return 0
    folder = Path(argv[0])
    top = pick_top20(folder)
    print("Z. 2018 거래대금 상위 20(스테이블·레버리지 제외): " + ", ".join(f"{s}" for s, _ in top))
    res = {}
    for s, _ in top:
        rows = [r for r in cs.load_csv(folder / f"{s}-1d.csv") if r[0] <= END]
        if not rows or rows[-1][0] < START:
            res[s] = {"note": "2019 전 폐지"}
            print(f"  {s}: 2019 전 폐지 — 시험 구간 없음")
            continue
        res[s] = per_coin(rows)
        x = res[s]
        print(f"  {s:10s} {x['start']}~{x['end']}{' 폐지' if x['delisted'] else ''}: v1 {x['ret']:+7.0%}·MDD {x['mdd']:5.1%}·비율 {x['ratio']:5.2f}·거래 {x['trades']:2d}·거래당 {x['ev']:+8.1f} | 보유 {x['bh_ret']:+7.0%}·MDD {x['bh_mdd']:5.1%}·비율 {x['bh_ratio']:5.2f}")
    tested = [x for x in res.values() if "ratio" in x]
    beat = sum(1 for x in tested if x["ratio"] > x["bh_ratio"])
    evs = sorted(x["ev"] for x in tested)
    med_ev = evs[len(evs) // 2] if evs else float("nan")
    ok_a = beat >= 0.6 * len(tested) and med_ev > 0
    print(f"\n(a) v1 비율 > 보유: {beat}/{len(tested)} · 종목 중앙 거래당 {med_ev:+.1f} → {'추세 효과가 사후 선택 밖에서도 나타남(가설)' if ok_a else 'BTC·ETH 결과는 생존편향에 기댈 수 있음 — 한계 강화'}")
    p = portfolio(load_dir(folder, [s for s, x in res.items() if "ratio" in x]))
    ok_b = p["ratio"] > p["bh_ratio"] and p["ratio"] > 0
    print(f"(b) 한 계좌 {len(tested)}종목: {p['ret']:+.0%}·MDD {p['mdd']:.1%}·비율 {p['ratio']:.2f} vs 같은 금액 보유 {p['bh_ret']:+.0%}·MDD {p['bh_mdd']:.1%}·비율 {p['bh_ratio']:.2f} → {'다종목 확장 근거(가설)' if ok_b else '확장 근거 없음'}")
    (LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-universe-z.json").write_text(
        json.dumps({"top20": top, "coins": res, "a": ok_a, "portfolio": p, "b": ok_b}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

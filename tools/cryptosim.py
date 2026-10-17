"""코인(바이낸스 현물) 단일 종목 추세 추종 시뮬레이터 — 일봉(UTC 00:00 경계) 근사, 판정 아님.

운영 M2 설계에 맞춤(읽기로 확인, 2026-10-17): BTCUSDT 1종목(A-096), 거래일 = UTC 날짜(A-055·D-108), 기준 통화 USDT, 현물만(레버리지·공매도 없음),
주문 단위 가격 0.01·수량 0.00001·최소 주문 5 USDT(테스트넷 exchangeInfo 예시, binance-spot.md) — **TICK 0.01은 BTC·ETH용. 저가 코인(가격 < 수 USDT)은 체결가를 왜곡하므로 호출 쪽에서 cs.TICK을 낮춘다(2026-10-18 Z에서 확인)**, 수수료 기본 0.1%(예시 요율 — 실제 계정 요율 미확인).
데이터: CSV(date 또는 open_time, open, high, low, close, volume[...]). date는 YYYY-MM-DD(UTC) 또는 밀리초 open_time. 운영 수집 형식이 오면 열 이름만 맞춘다.

규칙(파라미터):
- 진입: 종가 > 직전 entry_n일 최고 종가(돌파). regime_n > 0이면 종가 > SMA(regime_n)도 필요. 24/7이라 '오늘 종가 ≈ 다음 봉 시가' →
  체결 = 다음 봉 시가 × (1 + 슬리피지).
- 손절: stop_mode pct(매입가 × (1 − stop_pct)) / atr(매입가 − stop_atr × ATR14(진입 판정일)). stop_when intraday: 다음 봉부터 시가 ≤ 손절선이면 시가,
  저가 ≤ 손절선이면 손절선 가격 / close: 종가 < 손절선 → 다음 봉 시가.
- 청산: exit_mode sma(종가 < SMA(exit_n)) / low(종가 < 직전 exit_n일 최저 종가) / trail(종가 < 보유 중 최고 종가 − trail_atr × ATR14) → 다음 봉 시가.
- 크기: 자산 × min(max_weight, risk_ratio / (손절 거리 ÷ 가격)). max_weight ≤ 1(레버리지 없음). 수량 0.00001 내림, 5 USDT 미만이면 주문 없음.
- 국면 비중(bull_mode A: 종가 > SMA200 / B: + SMA200 상승(20일 전 대비)): 진입 판정일에 상승 국면이면 비중 = bull_weight, 아니면 위험 크기.
- 피라미딩(pyr_max > 1): 보유 중 종가 ≥ 마지막 매수가 + pyr_step × ATR(첫 판정일)이면 다음 봉 시가에 1단위(같은 위험 규칙) 추가,
  최대 pyr_max단위, 총 비중 ≤ max_weight. pyr_stop last = 손절선을 마지막 단위 기준으로 올림 / first = 첫 손절선 유지. 청산은 전량.
- 다른 계열(2026-10-17 추가, 기본값은 기존과 같음): entry_rule breakout(기본) / above_sma(종가 > SMA(entry_n)) / tsmom(종가 > entry_n일 전 종가) /
  rsi2(RSI(2, Wilder) < rsi_th). exit_mode tsmom(종가 ≤ exit_n일 전 종가) / mr(종가 > SMA(exit_n) — 역추세 이익 실현).
  entry_allow(집합)가 있으면 그 날짜에만 진입(외부 필터, 기본 None). hold_max > 0이면 보유 hold_max번째 종가에서 청산(체결일 종가 = 1번째). stop_mode none = 손절 없음·비중 max_weight.
- 비용: 수수료 fee(양방향), 슬리피지 slip. 세금 없음(적용 판단은 사용자 몫 — U-17).
비교 기준선: 같은 구간 그냥 보유(첫날 시가 매수 → 마지막 날 종가 평가, 수수료 1회).
실행: python tools/cryptosim.py --csv data/crypto/BTCUSDT-1d.csv [--start ...] [--end ...] [--set "키=값"] [--grid "키=값,값;..."]
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
STEP, MIN_NOTIONAL, TICK = 0.00001, 5.0, 0.01


def load_csv(path: Path) -> list[tuple[date, float, float, float, float, float]]:
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if "date" in r and r["date"]:
                d = date.fromisoformat(r["date"][:10])
            else:
                d = datetime.fromtimestamp(int(float(r["open_time"])) / 1000, tz=timezone.utc).date()
            rows.append((d, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r.get("volume") or 0)))
    rows.sort()
    for a, b in zip(rows, rows[1:]):
        if a[0] == b[0]:
            raise ValueError(f"중복 날짜 {a[0]}")
    return rows


def atr_series(rows: list, n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(rows)
    trs = []
    for k in range(1, len(rows)):
        _, _, h, l, _, _ = rows[k]
        pc = rows[k - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if len(trs) >= n:
            out[k] = sum(trs[-n:]) / n
    return out


def rsi_series(c: list[float], n: int = 2) -> list[float | None]:
    """Wilder RSI. 첫 n개 변화의 평균으로 시작, 이후 (이전×(n−1) + 현재)/n."""
    out: list[float | None] = [None] * len(c)
    if len(c) <= n:
        return out
    ch = [c[k] - c[k - 1] for k in range(1, len(c))]
    up = sum(max(x, 0.0) for x in ch[:n]) / n
    dn = sum(max(-x, 0.0) for x in ch[:n]) / n
    for k in range(n, len(c)):
        if k > n:
            x = ch[k - 1]
            up, dn = (up * (n - 1) + max(x, 0.0)) / n, (dn * (n - 1) + max(-x, 0.0)) / n
        out[k] = 100.0 if dn == 0 else 100.0 - 100.0 / (1 + up / dn)
    return out


def simulate(rows: list, P: dict, start: date, end: date) -> dict:
    c = [r[4] for r in rows]
    atr = atr_series(rows)
    rsi = rsi_series(c, 2) if P.get("entry_rule") == "rsi2" else None
    idx = [k for k, r in enumerate(rows) if start <= r[0] <= end]
    if not idx:
        raise ValueError("구간에 데이터 없음")
    cash, qty, entry_px, stop, peak_c = float(P["cash"]), 0.0, 0.0, 0.0, 0.0
    entry_day, held = None, 0
    units, last_add, atr0 = 0, 0.0, None                # 피라미딩: 단위 수·마지막 매수가·첫 판정일 ATR
    pend = None                                      # ("buy", stop_line) / ("sell", reason)
    trades, eq_curve = [], []
    peak_eq, mdd = cash, 0.0
    fee, slip = P["fee"], P["slip"]

    def sma(k: int, n: int) -> float | None:
        return sum(c[k - n + 1:k + 1]) / n if k + 1 >= n else None

    for k in idx:
        d, o, h, l, cl, _ = rows[k]
        # 1) 시가 체결
        if pend is not None:
            if pend[0] == "buy" and qty == 0:
                px = math.ceil(o * (1 + slip) / TICK) * TICK
                eq = cash
                sl = px * (1 - P["stop_pct"]) if P["stop_mode"] == "pct" else 0.0 if P["stop_mode"] == "none" else px - P["stop_atr"] * pend[1]   # 체결가 기준 손절선
                dist = (px - sl) / px
                w = min(P["max_weight"], P["risk_ratio"] / dist) if dist > 0 else 0.0
                if P["stop_mode"] == "none":
                    w, sl = P["max_weight"], 0.0
                if len(pend) > 2 and pend[2]:
                    w = min(P["max_weight"], P["bull_weight"])     # 상승 국면이면 위험 크기 대신 bull_weight
                q = math.floor(eq * w / (px * (1 + fee)) / STEP) * STEP
                if q * px >= MIN_NOTIONAL and dist > 0 and (sl > 0 or P["stop_mode"] == "none"):
                    cash -= q * px * (1 + fee)
                    qty, entry_px, stop, peak_c = q, px, sl, px
                    entry_day, held = d, 0
                    units, last_add, atr0 = 1, px, pend[1]
            elif pend[0] == "add" and qty > 0:
                px = math.ceil(o * (1 + slip) / TICK) * TICK
                eq = cash + qty * o
                sl = px * (1 - P["stop_pct"]) if P["stop_mode"] == "pct" else px - P["stop_atr"] * atr0
                dist = (px - sl) / px
                room = P["max_weight"] - qty * o / eq           # 레버리지 없음: 총 비중 ≤ max_weight
                w = min(room, P["risk_ratio"] / dist) if dist > 0 else 0.0
                q = math.floor(min(eq * w, cash) / (px * (1 + fee)) / STEP) * STEP
                if w > 0 and q * px >= MIN_NOTIONAL:
                    cash -= q * px * (1 + fee)
                    entry_px = (entry_px * qty + px * q) / (qty + q)
                    qty += q
                    units, last_add = units + 1, px
                    if P["pyr_stop"] == "last":
                        stop = max(stop, sl)
            elif pend[0] == "sell" and qty > 0:
                px = math.floor(o * (1 - slip) / TICK) * TICK
                cash += qty * px * (1 - fee)
                trades.append((str(entry_day), str(d), entry_px, px, qty, pend[1]))
                qty = 0.0
            pend = None
        # 2) 장중 손절
        if qty > 0 and P["stop_when"] == "intraday" and d != entry_day:
            ref = o if o <= stop else (stop if l <= stop else None)
            if ref is not None:
                px = math.floor(ref * (1 - slip) / TICK) * TICK
                cash += qty * px * (1 - fee)
                trades.append((str(entry_day), str(d), entry_px, px, qty, "stop_intraday"))
                qty = 0.0
        # 3) 종가 판정
        if qty > 0:
            peak_c = max(peak_c, cl)
            held += 1
            why = None
            if P["stop_when"] == "close" and cl < stop:
                why = "stop_close"
            elif P["exit_mode"] == "sma":
                s = sma(k, P["exit_n"])
                if s is not None and cl < s:
                    why = "sma"
            elif P["exit_mode"] == "low":
                if k >= P["exit_n"] and cl < min(c[k - P["exit_n"]:k]):
                    why = "low"
            elif P["exit_mode"] == "trail":
                if atr[k] is not None and cl < peak_c - P["trail_atr"] * atr[k]:
                    why = "trail"
            elif P["exit_mode"] == "tsmom":
                if k >= P["exit_n"] and cl <= c[k - P["exit_n"]]:
                    why = "tsmom"
            elif P["exit_mode"] == "mr":
                s = sma(k, P["exit_n"])
                if s is not None and cl > s:
                    why = "mr"
            if not why and P["hold_max"] > 0 and held >= P["hold_max"]:
                why = "hold_max"
            if why:
                pend = ("sell", why)
            elif units < P["pyr_max"] and atr0 is not None and cl >= last_add + P["pyr_step"] * atr0:
                pend = ("add", None)                     # 마지막 매수가 + pyr_step × ATR(첫 판정일) 이상 → 다음 봉 시가에 1단위 추가
        elif k >= P["entry_n"]:
            rule = P["entry_rule"]
            if rule == "breakout":
                ok = cl > max(c[k - P["entry_n"]:k])
            elif rule == "above_sma":
                s = sma(k, P["entry_n"])
                ok = s is not None and cl > s
            elif rule == "tsmom":
                ok = cl > c[k - P["entry_n"]]
            elif rule == "rsi2":
                ok = rsi[k] is not None and rsi[k] < P["rsi_th"]
            else:
                raise ValueError(f"entry_rule 모름: {rule}")
            if ok and P["entry_allow"] is not None:
                ok = str(d) in P["entry_allow"]          # 외부에서 계산한 진입 허용 날짜(예: 볼륨 프로파일 수용) — 판정일 기준
            if ok and P["regime_n"] > 0:
                s = sma(k, P["regime_n"])
                ok = s is not None and cl > s
            if ok and atr[k] is not None:
                bull = False
                if P["bull_mode"] in ("A", "B"):
                    s200, s200p = sma(k, 200), sma(k - 20, 200) if k >= 220 else None
                    bull = s200 is not None and cl > s200 and (P["bull_mode"] == "A" or (s200p is not None and s200 > s200p))
                pend = ("buy", atr[k], bull)             # 손절선은 다음 봉 시가 체결가 기준(ATR은 판정일 값), bull = 국면 비중
        eq = cash + qty * cl
        eq_curve.append((str(d), round(eq, 2)))
        peak_eq = max(peak_eq, eq)
        mdd = max(mdd, (peak_eq - eq) / peak_eq if peak_eq > 0 else 0.0)
    # 기준선: 그냥 보유
    o0 = rows[idx[0]][1] * (1 + slip)
    bh = P["cash"] / (o0 * (1 + fee)) * c[idx[-1]]
    bh_peak, bh_mdd = 0.0, 0.0
    for k in idx:
        v = P["cash"] / (o0 * (1 + fee)) * c[k]
        bh_peak = max(bh_peak, v)
        bh_mdd = max(bh_mdd, (bh_peak - v) / bh_peak)
    rets = [t[3] / t[2] * (1 - fee) / (1 + fee) - 1 for t in trades]
    by_year: dict[str, float] = {}
    for dstr, v in eq_curve:
        by_year[dstr[:4]] = v
    yr, last = {}, float(P["cash"])
    for y in sorted(by_year):
        yr[y] = round(by_year[y] / last - 1, 4)
        last = by_year[y]
    return {"final": eq_curve[-1][1], "ret": eq_curve[-1][1] / P["cash"] - 1, "mdd": mdd, "trades": len(trades),
            "win_rate": sum(1 for r in rets if r > 0) / len(rets) if rets else 0.0,
            "avg_ret": sum(rets) / len(rets) if rets else 0.0, "year_ret": yr,
            "buy_hold_ret": bh / P["cash"] - 1, "buy_hold_mdd": bh_mdd,
            "exposure": None, "trade_list": trades, "eq_curve": eq_curve}


DEFAULTS = {"cash": 10000.0, "entry_n": 20, "regime_n": 0, "stop_mode": "pct", "stop_pct": 0.08, "stop_atr": 3.0,
            "stop_when": "intraday", "exit_mode": "sma", "exit_n": 20, "trail_atr": 3.0, "risk_ratio": 0.02,
            "max_weight": 1.0, "fee": 0.001, "slip": 0.0005,
            "pyr_max": 1, "pyr_step": 1.0, "pyr_stop": "last", "bull_mode": "off", "bull_weight": 0.98,
            "entry_rule": "breakout", "rsi_th": 10.0, "hold_max": 0, "entry_allow": None}
NUM = {"cash", "stop_pct", "stop_atr", "trail_atr", "risk_ratio", "max_weight", "fee", "slip", "pyr_step", "bull_weight", "rsi_th"}
INT = {"entry_n", "regime_n", "exit_n", "pyr_max", "hold_max"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--start", default="2017-09-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--set", default="")
    ap.add_argument("--grid", default="")
    ap.add_argument("--name", default="cryptosim")
    ap.add_argument("--allow-2026", action="store_true", help="합성 데이터 시험용. 실제 데이터 탐색에는 쓰지 않는다(최종 확인 구간)")
    ns = ap.parse_args(argv)
    if date.fromisoformat(ns.end) >= date(2026, 1, 1) and not ns.allow_2026:
        print("2026 이후는 최종 확인 구간 — 탐색에 쓰지 않는다(운영 D-163과 같은 원칙)")
        return 2
    conv = lambda k, x: float(x) if k in NUM else int(x) if k in INT else x  # noqa: E731
    base = dict(DEFAULTS)
    for part in [p for p in ns.set.split(";") if p.strip()]:
        k, x = part.split("=", 1)
        base[k.strip()] = conv(k.strip(), x.strip())
    grid = [(k.strip(), [conv(k.strip(), x.strip()) for x in vs.split(",")])
            for k, vs in (p.split("=", 1) for p in ns.grid.split(";") if p.strip())]
    combos = [dict(zip([k for k, _ in grid], v)) for v in itertools.product(*[vs for _, vs in grid])] or [{}]
    rows = load_csv(Path(ns.csv))
    out = []
    t0 = time.monotonic()
    for cmb in combos:
        P = dict(base, **cmb)
        r = simulate(rows, P, date.fromisoformat(ns.start), date.fromisoformat(ns.end))
        r["params"] = P
        r.pop("eq_curve")
        if len(combos) > 1:
            r.pop("trade_list")
        out.append(r)
        if len(combos) <= 30:
            lab = " ".join(f"{k}={v}" for k, v in cmb.items()) or "기본"
            print(f"[{lab}] 수익 {r['ret']:+.1%} MDD {r['mdd']:.1%} 거래 {r['trades']} 승률 {r['win_rate']:.0%} 거래당 {r['avg_ret']:+.2%} "
                  f"| 그냥 보유 {r['buy_hold_ret']:+.1%} MDD {r['buy_hold_mdd']:.1%}")
    print(f"{len(combos)}조합 {time.monotonic() - t0:.1f}초 · 근사(일봉), 판정 아님")
    res = LAB / "results" / "cryptosim"
    res.mkdir(parents=True, exist_ok=True)
    (res / f"{date.today():%Y%m%d}-{ns.name}.json").write_text(json.dumps(out, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""전략실 빠른 시뮬레이터 — r3-trend 계열(52주 신고가·조정 돌파 없이 신고가 진입 위주) 포트폴리오를 일봉으로 빠르게 근사한다.

목적: 체결 시점(다음 날 시가 vs 당일 종가, 종가 확인 손절 vs 장중 손절)과 필터·크기를 빠르게 그리드 탐색. **근사 결과**이며 판정이 아니다.
운영 엔진(quick/validate)과 다른 점은 아래 '근사'에 적는다. 운영 엔진 모드(--entry next_open --stop close)로 엔진 결과와 대조해 차이를 기록한 뒤 쓴다.

규칙(전략 v13 high52·exit sma와 같은 의미):
- 판정: 매 거래일 종가 기준. 진입 후보 = 전 종목 중 데이터 253행 이상, 미보유, 오늘 종가 > 직전 251일 최고 종가(그 전 fresh_n일 종가 모두 그 미만),
  거래량 ≥ 50일 평균 × vol_mult(0 = 없음), RS 백분위 ≥ rs_min, 정배열(align), 20일 평균 거래대금 ≥ min_turnover(억).
  빈자리(max_pos − 보유 수, 판정 시점 보유 기준) 수만큼 rank_by 순(rs·turnover·day_ret).
- 청산: 손절선 = 매입가 × (1 − stop_pct). stop=close: 종가 < 손절선 → 다음 날 시가 매도 / stop=intraday: 다음 날부터 시가 ≤ 손절선이면 시가,
  저가 ≤ 손절선이면 손절선 가격에 매도. 종가 < SMA(exit_sma_n) → exit=next_open이면 다음 날 시가, exit=close면 그날 종가 매도. 보유 hold_max일 만료.
- 체결: entry=next_open → 다음 날 시가 × (1+슬리피지), entry=close → 그날 종가 × (1+슬리피지)(종가를 보고 종가에 사는 낙관 근사).
  매도 가격 × (1−슬리피지). 거래량 상한 = 체결일 거래량 × volume_cap. 다음 날 시가가 상한가(전일 종가 × 1.3 이상)면 매수 미체결,
  entry=close에서 종가가 상한가(전일 × 1.295 이상)면 미체결(상한가 잔량 근사).
- 크기: 기준 금액 = 전일 종가 평가 자산. 수량 = min(기준×risk_ratio/(가격×stop_pct), 기준×max_weight/가격, 거래량 상한).
  현금 예약 = 수량 × 전일 종가 × 1.3 × (1+수수료)(운영 게이트의 상한가 예약 근사) ≤ 판정 시점 현금(같은 판정의 매도 대금은 아직 없음).
  하루 신규 주문 ≤ max_new. 일일 손실 정지: 시가 평가 자산이 기준 대비 −l4 이하면 그날 신규 진입 없음.
- 비용: 수수료 0.015%(양방향), 매도세 0.20%, 슬리피지 0.1%.
근사(운영 엔진과 다름): 호가 단위 반올림 없음, 게이트 L1·L2·L3·L7은 현금 예약·비중 상한으로만 근사, 품질 검사(30% 변동 등) 없음 —
  data/krall은 30% 손질 뒤 13종목만 이상치(여기서는 계속 씀), 판정 시점 정의(엔진은 09:30에 전일까지 봉) — next_open 모드가 같은 의미.
실행: python tools/fastsim.py --data data/krall --start 2017-01-01 --end 2025-12-31 [옵션] [--grid "키=값,값;키=값"]
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
import time
from bisect import bisect_left
from collections import deque
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
COMM, TAX, SLIP = 0.00015, 0.0020, 0.001
H52 = 251
RS_LAGS = (63, 126, 189, 252)


# --- 데이터·지표 (종목별 1회) -----------------------------------------------------------------------

class Stock:
    __slots__ = ("code", "d", "o", "h", "l", "c", "v", "pos", "h52new", "rs", "dal", "wal", "vavg", "turn", "sma", "bad", "brk")

    def __init__(self, code: str, rows: list[list[str]], sma_ns: tuple[int, ...], fresh_ns: tuple[int, ...],
                 cal_set: set | None = None, ca_col: int | None = None) -> None:
        self.code = code
        self.d = [date.fromisoformat(r[0]) for r in rows]
        self.o = [float(r[1]) for r in rows]
        self.h = [float(r[2]) for r in rows]
        self.l = [float(r[3]) for r in rows]
        self.c = [float(r[4]) for r in rows]
        self.v = [float(r[5]) for r in rows]
        n = len(self.c)
        c, v = self.c, self.v
        # 운영 품질 검사(preprocess_daily) 근사: 처음 실패하는 행 이후로는 판정에서 뺀다(data_ok False — 진입·청산 판정 모두 없음)
        self.bad = n
        cal_l = sorted(cal_set) if cal_set else None
        for k in range(n):
            r = rows[k]
            ca = ca_col is not None and len(r) > ca_col and r[ca_col].strip() in ("1", "true", "y")
            if min(self.o[k], self.h[k], self.l[k], c[k]) <= 0 or v[k] < 0 or not (self.l[k] <= min(self.o[k], c[k]) and max(self.o[k], c[k]) <= self.h[k]):
                self.bad = k; break
            if cal_set is not None and self.d[k] not in cal_set:
                self.bad = max(k, 1); break
            if k:
                if self.d[k] == self.d[k - 1]:
                    self.bad = k; break
                if c[k - 1] > 0 and not ca and abs(c[k] - c[k - 1]) / c[k - 1] > 0.30 + 1e-12:
                    self.bad = k; break
                if cal_l is not None:
                    i0, i1 = bisect_left(cal_l, self.d[k - 1]), bisect_left(cal_l, self.d[k])
                    if i1 - i0 > 1:                              # 사이에 빠진 거래일
                        self.bad = k; break
        pre = [0.0]
        for x in c:
            pre.append(pre[-1] + x)
        sm = lambda k, m: (pre[k + 1] - pre[k + 1 - m]) / m if k + 1 >= m else None  # noqa: E731
        self.sma = {m: [sm(k, m) for k in range(n)] for m in set(sma_ns) | {20, 60, 120}}
        # 52주 신고가: 오늘 종가 > 직전 251일 최고 종가, fresh_n별로 '그 전 fresh_n일 종가 모두 H52 미만'
        self.h52new = {f: [False] * n for f in fresh_ns}
        dq: deque = deque()
        for k in range(n):
            while dq and dq[0] < k - H52:
                dq.popleft()
            if k >= H52 + 1 - 1 and len(dq) and k >= H52:
                hk = c[dq[0]]                                       # 직전 251일(k-251..k-1) 최고 종가
                if c[k] > hk:
                    for f in fresh_ns:
                        ok = True
                        if f > 0:
                            for j in range(max(0, k - f), k):
                                if c[j] >= hk:
                                    ok = False
                                    break
                        self.h52new[f][k] = ok
            while dq and c[dq[-1]] <= c[k]:
                dq.pop()
            dq.append(k)
        self.rs = [None] * n
        for k in range(RS_LAGS[-1], n):
            try:
                self.rs[k] = 2 * (c[k] / c[k - 63] - 1) + (c[k] / c[k - 126] - 1) + (c[k] / c[k - 189] - 1) + (c[k] / c[k - 252] - 1)
            except ZeroDivisionError:
                self.rs[k] = None
        s20, s60, s120 = self.sma[20], self.sma[60], self.sma[120]
        self.dal = [s120[k] is not None and c[k] > s20[k] > s60[k] > s120[k] for k in range(n)]
        # 주봉 정배열: ISO 주별 마지막 종가(진행 중 주는 오늘 종가), 주봉 종가 > 10주 SMA > 30주 SMA
        self.wal = [False] * n
        done: list[float] = []
        pw = [0.0]
        key = None
        for k in range(n):
            wk = self.d[k].isocalendar()[:2]
            if key is not None and wk != key:
                done.append(c[k - 1])
                pw.append(pw[-1] + c[k - 1])
            key = wk
            m = len(done)
            if m >= 29:
                s10 = (pw[m] - pw[m - 9] + c[k]) / 10
                s30 = (pw[m] - pw[m - 29] + c[k]) / 30
                self.wal[k] = c[k] > s10 > s30
        vp = [0.0]
        for x in v:
            vp.append(vp[-1] + x)
        self.vavg = [(vp[k] - vp[k - 50]) / 50 if k >= 50 else None for k in range(n)]   # 직전 50일(오늘 제외)
        tp = [0.0]
        for x, y in zip(c, v):
            tp.append(tp[-1] + x * y)
        self.turn = [(tp[k + 1] - tp[k - 19]) / 20 / 1e8 if k >= 19 else 0.0 for k in range(n)]   # 억 원
        self.pos = {dd: k for k, dd in enumerate(self.d)}
        self.brk: dict[int, list[bool]] = {}           # brk_n별 "종가 > 직전 n일 종가 최고"(필요할 때 계산)

    def breakout(self, n: int) -> list[bool]:
        if n not in self.brk:
            c, out, dq = self.c, [False] * len(self.c), deque()
            for k in range(len(c)):
                while dq and dq[0] < k - n:
                    dq.popleft()
                if k >= n and dq:
                    out[k] = c[k] > c[dq[0]]
                while dq and c[dq[-1]] <= c[k]:
                    dq.pop()
                dq.append(k)
            self.brk[n] = out
        return self.brk[n]


def load(data: Path, sma_ns: tuple[int, ...], fresh_ns: tuple[int, ...]) -> tuple[list[date], list[Stock]]:
    cal = [date.fromisoformat(r["date"]) for r in csv.DictReader((data / "KOSPI.csv").open(encoding="utf-8"))]
    stocks = []
    for p in sorted(data.glob("*.csv")):
        if p.stem == "KOSPI":
            continue
        with p.open(encoding="utf-8") as f:
            allr = [r for r in csv.reader(f)]
        hdr, rows = allr[0], allr[1:]
        ca_col = hdr.index("corporate_action") if "corporate_action" in hdr else None
        if len(rows) >= 253:
            stocks.append(Stock(p.stem, rows, sma_ns, fresh_ns, set(cal), ca_col))
    return cal, stocks


# --- 시뮬레이션 ---------------------------------------------------------------------------------------

_BANDS = ((2000, 1), (5000, 5), (20000, 10), (50000, 50), (200000, 100), (500000, 500), (float("inf"), 1000))  # 운영 config/ticks/krx.toml STOCK


def tick(p: float) -> float:
    for below, t in _BANDS:
        if p < below:
            return t
    return 1000


def limits(prev_close: float) -> tuple[float, float]:
    """상·하한가: 기준가 × (1 ± 0.30)을 호가 단위로 내림·올림(운영 price_limits 근사)."""
    up, lo = prev_close * 1.3, prev_close * 0.7
    return math.floor(up / tick(up)) * tick(up), math.ceil(lo / tick(lo)) * tick(lo)


def fill_px(raw_ref: float, buy: bool, up: float, lo: float) -> float:
    raw = raw_ref * (1 + SLIP) if buy else raw_ref * (1 - SLIP)
    u = tick(raw)
    px = (math.ceil(raw / u - 1e-9) if buy else math.floor(raw / u + 1e-9)) * u
    return min(px, up) if buy else max(px, lo)


def simulate(cal: list[date], stocks: list[Stock], P: dict, start: date, end: date) -> dict:
    """하루 = [09:30 판정(전일 종가까지)·시가 체결 — next_open 모드는 엔진과 같은 의미] → [장중 손절] → [종가 판정(close 모드)]."""
    cash = float(P["cash"])
    held: dict[int, dict] = {}            # 종목 번호 → {qty, px, d0, k0}
    trades = []
    days = [d for d in cal if start <= d <= end]
    peak = prev_eq = cash
    mdd = 0.0
    stop_pct, sma_n, max_pos, fresh = P["stop_pct"], P["exit_sma_n"], P["max_pos"], P["fresh_n"]
    eq_curve: list = []
    halt_days: list = []

    def cands_on(kof, exclude) -> list[tuple[int, int]]:
        out, rs_today = [], []
        for si, s in enumerate(stocks):
            k = kof(s)
            if k is None or k < 252 or k >= s.bad:
                continue
            if s.rs[k] is not None:
                rs_today.append(s.rs[k])
            sig = s.breakout(P["brk_n"])[k] if P["brk_n"] else s.h52new[fresh][k]   # brk_n > 0: N일 종가 돌파(2026-10-18 X)
            if si in exclude or not sig:          # 엔진 전략과 같게: 거래량 0(정지일)도 후보에서 빼지 않음
                continue
            if P["gate_sma"] and (s.sma[P["gate_sma"]][k] is None or s.c[k] <= s.sma[P["gate_sma"]][k]):
                continue
            if P["vol_mult"] > 0 and (s.vavg[k] is None or s.v[k] < P["vol_mult"] * s.vavg[k]):
                continue
            if P["align"] in ("both", "daily") and not s.dal[k]:
                continue
            if P["align"] in ("both", "weekly") and not s.wal[k]:
                continue
            if P["min_turnover"] > 0 and s.turn[k] < P["min_turnover"]:
                continue
            out.append((si, k))
        if out and P["rs_min"] > 0:
            rs_today.sort()
            nrs = len(rs_today)
            out = [(si, k) for si, k in out if stocks[si].rs[k] is not None and
                   bisect_left(rs_today, stocks[si].rs[k]) * 100 / max(1, nrs - 1) >= P["rs_min"]]
        if P["rank_by"] == "rs":
            keyf = lambda t: stocks[t[0]].rs[t[1]] if stocks[t[0]].rs[t[1]] is not None else -9  # noqa: E731
        elif P["rank_by"] == "turnover":
            keyf = lambda t: stocks[t[0]].turn[t[1]]  # noqa: E731
        else:
            keyf = lambda t: stocks[t[0]].c[t[1]] / stocks[t[0]].c[t[1] - 1] - 1  # noqa: E731
        out.sort(key=lambda t: (-keyf(t), stocks[t[0]].code))
        return out

    def sell(si: int, px: float, day: date, why: str, kt: int | None = None) -> None:
        """거래량 상한(그날 거래량 × volume_cap, 엔진과 같음)까지만 체결 — 나머지는 보유로 남아 다음 판정에서 다시 매도."""
        nonlocal cash
        h = held[si]
        q = h["qty"]
        if kt is not None:
            q = min(q, int(stocks[si].v[kt] * P["volume_cap"]))
        if q <= 0:
            return
        cash += q * px * (1 - COMM - TAX)
        trades.append((stocks[si].code, h["d0"], day, h["px"], px, q, why))
        if q < h["qty"]:
            h["qty"] -= q
        else:
            del held[si]

    def mark(si: int, h: dict, day: date, prev: bool) -> float:
        s = stocks[si]
        k = s.pos.get(day)
        if k is None:
            j = bisect_left(s.d, day) - 1
            return h["qty"] * (s.c[j] if j >= 0 else h["px"])
        return h["qty"] * (s.c[k - 1] if prev and k > 0 else s.c[k])

    for day in days:
        base = prev_eq                                         # 기준 금액 = 전일 종가 평가 자산
        def prevk(s, day=day):
            k = s.pos.get(day)
            return k - 1 if k is not None and k > 0 else None
        # --- 09:30 판정(전일 종가까지) + 시가 체결 ---
        eq_open = cash + sum((h["qty"] * stocks[si].o[stocks[si].pos[day]]) if day in stocks[si].pos else mark(si, h, day, False)
                             for si, h in held.items())
        halted = (eq_open - base) / base <= -P["l4"]
        if halted:
            halt_days.append((str(day), round((base - eq_open) / base, 4)))
        exits_now, n_held_decision = [], len(held)
        for si, h in held.items():
            s = stocks[si]
            k = prevk(s)
            if k is None or k >= s.bad:
                continue
            why = None
            if (k - h["k0"] + 1) >= P["hold_max"]:
                why = "expire"
            elif P["stop"] == "close" and s.c[k] < h["px"] * (1 - stop_pct):
                why = "stop_close"
            elif P["exit"] == "next_open" and s.sma[sma_n][k] is not None and s.c[k] < s.sma[sma_n][k]:
                why = "sma"
            if why:
                exits_now.append((si, why))
        entries = []
        free = 0
        if P["entry"] == "next_open" and not halted:
            free = max_pos - n_held_decision
            if free > 0:
                entries = cands_on(prevk, held)
        avail = cash
        n_new = 0
        reserved_total = 0.0
        held_val = sum(mark(si, h, day, True) for si, h in held.items())
        orders = []
        for si, k in entries:
            if free <= 0:
                break
            s = stocks[si]
            kt = s.pos[day]
            price = s.o[kt]
            stop = math.floor(price * (1 - stop_pct))
            if stop <= 0 or stop >= price:
                continue
            qty = int(min(math.floor(base * P["risk_ratio"] / (price - stop)), math.floor(base * P["max_weight"] / price),
                          math.floor(P["order_cap"] / (price * 1.3))))
            if qty <= 0:
                continue
            free -= 1                                          # 신호 = 자리 소비(게이트 거부여도)
            up, _ = limits(s.c[kt - 1])
            notional = qty * up
            need = notional * (1 + COMM)
            if (n_new >= P["max_new"] or (price * 1.03 - stop) * qty > P["l1"] * base or notional > P["l7"] * base
                    or notional > P["l2"] * base or held_val + reserved_total + notional > P["l3"] * base or need > avail):
                continue
            n_new += 1
            avail -= need
            reserved_total += notional
            orders.append((si, qty))
        for si, why in exits_now:                              # 시가 체결: 매도 → 매수
            s = stocks[si]
            kt = s.pos.get(day)
            if kt is None or s.v[kt] <= 0:
                continue
            up, lo = limits(s.c[kt - 1])
            if s.o[kt] <= lo:
                continue                                       # 하한가 시가 매도 미체결(엔진과 같음) — 다음 날 재판정
            sell(si, fill_px(s.o[kt], False, up, lo), day, why, kt)
        for si, qty in orders:
            s = stocks[si]
            kt = s.pos[day]
            up, lo = limits(s.c[kt - 1])
            if s.o[kt] >= up:
                continue                                       # 상한가 시가 매수 미체결
            q = min(qty, int(s.v[kt] * P["volume_cap"]))
            if q <= 0:
                continue
            px = fill_px(s.o[kt], True, up, lo)
            cash -= q * px * (1 + COMM)
            held[si] = {"qty": q, "px": px, "d0": day, "k0": kt}
        # --- 장중 손절 ---
        if P["stop"] == "intraday":
            for si in list(held):
                s, h = stocks[si], held[si]
                kt = s.pos.get(day)
                if kt is None or kt <= h["k0"] or s.v[kt] <= 0 or kt >= s.bad:
                    continue
                sl = h["px"] * (1 - stop_pct)
                ref = s.o[kt] if s.o[kt] <= sl else (sl if s.l[kt] <= sl else None)
                if ref is not None:
                    up, lo = limits(s.c[kt - 1])
                    if ref <= lo:
                        continue                               # 하한가에서는 매도 미체결 근사
                    sell(si, fill_px(ref, False, up, lo), day, "stop_intraday", kt)
        # --- 종가 판정(close 모드): SMA 종가 청산·종가 진입 ---
        if P["exit"] == "close":
            for si in list(held):
                s, h = stocks[si], held[si]
                kt = s.pos.get(day)
                if kt is None or kt <= h["k0"] or kt >= s.bad or s.sma[sma_n][kt] is None:
                    continue
                if s.c[kt] < s.sma[sma_n][kt]:
                    up, lo = limits(s.c[kt - 1])
                    if s.c[kt] <= lo:
                        continue                               # 하한가 마감 → 매도 미체결 근사
                    sell(si, fill_px(s.c[kt], False, up, lo), day, "sma_close", kt)
        if P["entry"] == "close" and not halted:
            free = max_pos - len(held)
            n_new = 0
            for si, kt in cands_on(lambda s, day=day: s.pos.get(day), held):
                if free <= 0 or n_new >= P["max_new"]:
                    break
                s = stocks[si]
                up, lo = limits(s.c[kt - 1])
                if s.c[kt] >= up:
                    continue                                   # 상한가 마감 → 미체결 근사
                price = s.c[kt]
                stop = math.floor(price * (1 - stop_pct))
                qty = int(min(math.floor(base * P["risk_ratio"] / (price - stop)), math.floor(base * P["max_weight"] / price)))
                q = min(qty, int(s.v[kt] * P["volume_cap"]))
                px = fill_px(price, True, up, lo)
                q = min(q, int(cash / (px * (1 + COMM))))
                if q <= 0:
                    continue
                cash -= q * px * (1 + COMM)
                held[si] = {"qty": q, "px": px, "d0": day, "k0": kt}
                free -= 1
                n_new += 1
        eq = cash + sum(mark(si, h, day, False) for si, h in held.items())
        eq_curve.append((str(day), round(eq)))
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak if peak > 0 else 0)
        prev_eq = eq
    pnl = [t[5] * (t[4] * (1 - COMM - TAX) - t[3] * (1 + COMM)) for t in trades]
    by_year: dict[int, float] = {}
    for t, x in zip(trades, pnl):
        by_year[t[2].year] = by_year.get(t[2].year, 0.0) + x
    return {"trades": len(trades), "win_rate": sum(1 for x in pnl if x > 0) / len(trades) if trades else 0.0,
            "pnl": sum(pnl), "final_equity": prev_eq, "mdd": mdd, "by_year": {y: round(v) for y, v in sorted(by_year.items())},
            "avg_ret_value_weighted": (sum(pnl) / sum(t[3] * t[5] for t in trades)) if trades else 0.0,
            "exit_reasons": {r: sum(1 for t in trades if t[6] == r) for r in {t[6] for t in trades}},
            "open_positions": len(held), "equity": eq_curve, "halt_days": halt_days,
            "trade_list": [(t[0], str(t[1]), str(t[2]), round(t[3], 2), round(t[4], 2), t[5], t[6]) for t in trades]}


DEFAULTS = {"cash": 1e8, "stop_pct": 0.08, "exit_sma_n": 20, "max_pos": 3, "fresh_n": 0, "vol_mult": 0.0, "align": "both",
            "rs_min": 0.0, "min_turnover": 0.0, "rank_by": "rs", "risk_ratio": 0.01, "max_weight": 0.20, "hold_max": 250,
            "order_cap": 1e8, "volume_cap": 0.10, "max_new": 5, "l1": 0.02, "l2": 0.30, "l3": 1.00, "l4": 0.03, "l7": 0.20,
            "entry": "next_open", "stop": "close", "exit": "next_open", "brk_n": 0, "gate_sma": 0}
NUM = {"cash", "stop_pct", "vol_mult", "rs_min", "min_turnover", "risk_ratio", "max_weight", "volume_cap", "l1", "l2", "l3",
       "l4", "l7", "order_cap"}
INT = {"exit_sma_n", "max_pos", "fresh_n", "hold_max", "max_new", "brk_n", "gate_sma"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(LAB / "data" / "krall"))
    ap.add_argument("--start", default="2017-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--set", default="", help='고정값 "키=값;키=값"')
    ap.add_argument("--grid", default="", help='그리드 "키=값,값;키=값,값"')
    ap.add_argument("--name", default="fastsim")
    ns = ap.parse_args(argv)
    if date.fromisoformat(ns.end) >= date(2026, 1, 1):
        print("2026 이후는 최종 확인 구간(D-163) — 탐색에 쓰지 않는다")
        return 2
    base = dict(DEFAULTS)
    conv = lambda k, x: float(x) if k in NUM else int(x) if k in INT else x  # noqa: E731
    for part in [p for p in ns.set.split(";") if p.strip()]:
        k, x = part.split("=", 1)
        base[k.strip()] = conv(k.strip(), x.strip())
    grid = [(k.strip(), [conv(k.strip(), x.strip()) for x in vs.split(",")])
            for k, vs in (p.split("=", 1) for p in ns.grid.split(";") if p.strip())]
    combos = [dict(zip([k for k, _ in grid], vals)) for vals in itertools.product(*[v for _, v in grid])] or [{}]
    sma_ns = tuple({base["exit_sma_n"]} | {c.get("exit_sma_n", base["exit_sma_n"]) for c in combos}
                   | {g for g in [base["gate_sma"]] + [c.get("gate_sma", 0) for c in combos] if g})
    fresh_ns = tuple({base["fresh_n"]} | {c.get("fresh_n", base["fresh_n"]) for c in combos})
    t0 = time.monotonic()
    cal, stocks = load(Path(ns.data), sma_ns, fresh_ns)
    print(f"적재 {len(stocks)}종목 {time.monotonic() - t0:.0f}초 · 근사 시뮬레이터(판정 아님, 생존편향 포함)")
    out = []
    for cmb in combos:
        P = dict(base, **cmb)
        t1 = time.monotonic()
        r = simulate(cal, stocks, P, date.fromisoformat(ns.start), date.fromisoformat(ns.end))
        r.update(params={k: P[k] for k in P}, seconds=round(time.monotonic() - t1, 1))
        if len(combos) > 1:                                    # 그리드: 결과 파일 크기 — 거래 목록·자산 곡선 빼고 저장
            r.pop("trade_list", None)
            r.pop("equity", None)
        out.append(r)
        lab = " ".join(f"{k}={v}" for k, v in cmb.items()) or "기본"
        pos_years = sum(1 for v in r["by_year"].values() if v > 0)
        if len(combos) > 30:
            continue
        print(f"[{lab}] {r['trades']}건 승률 {r['win_rate']:.1%} 손익 {r['pnl']/1e4:,.0f}만 MDD {r['mdd']:.1%} "
              f"손익/MDD {r['pnl']/1e4/max(1e-9, r['mdd']*100):,.0f} 양수 {pos_years}/{len(r['by_year'])} 금액가중 거래당 {r['avg_ret_value_weighted']:+.2%} "
              f"청산 {r['exit_reasons']} ({r['seconds']}초)")
    res_dir = LAB / "results" / "fastsim"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / f"{date.today():%Y%m%d}-{ns.name}.json").write_text(json.dumps(out, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

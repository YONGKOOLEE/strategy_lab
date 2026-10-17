"""BTC 장중 후보 3개 — 1시간 판정 시뮬레이션 (판정 아님). 사전 등록 research/2026-10-18-intraday-design.md (2026-10-18 00:49).

실행 모형: 매 1시간 봉 종가에 판정 → 다음 봉 시가 × (1 ± 슬리피지) 체결. 손절·목표가는 장중 확인(시가가 넘었으면 시가, 아니면 그 가격),
한 봉에서 둘 다 닿으면 손절 먼저. 수수료 0.1% 양방향, 목표가(지정가) 체결에는 슬리피지 없음.
  python research/btc_intraday_study.py   → 표준출력 + results/cryptosim/<날짜>-intraday.json
"""

from __future__ import annotations

import json
import math
import statistics as st
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_monitor_study import load_hours  # noqa: E402
from btc_vp_study import BINS, value_area  # noqa: E402

FEE, STEP = 0.001, 0.00001
TRAIN = (date(2017, 9, 1), date(2021, 12, 31))
CONF = (date(2022, 1, 1), date(2025, 12, 31))
FULL = (date(2017, 9, 1), date(2025, 12, 31))


class Data:
    def __init__(self) -> None:
        self.hours = [h for h in load_hours(LAB / "data" / "crypto" / "BTCUSDT-1h.csv") if h[0].date() <= FULL[1]]
        days: dict[date, list[float]] = {}
        for t, o, h, l, c, _ in self.hours:
            b = days.get(t.date())
            if b is None:
                days[t.date()] = [o, h, l, c]
            else:
                b[1], b[2], b[3] = max(b[1], h), min(b[2], l), c
        self.dates = sorted(days)
        self.di = {d: k for k, d in enumerate(self.dates)}
        self.d = [days[d] for d in self.dates]          # [o, h, l, c]
        cl = [x[3] for x in self.d]
        tr = [None] + [max(self.d[k][1] - self.d[k][2], abs(self.d[k][1] - cl[k - 1]), abs(self.d[k][2] - cl[k - 1])) for k in range(1, len(cl))]
        self.cl = cl
        self.atr = [sum(tr[k - 13:k + 1]) / 14 if k >= 14 else None for k in range(len(cl))]   # 날짜 k까지 포함한 ATR14
        va = {}
        with BINS.open(encoding="utf-8") as f:
            for line in f:
                o = json.loads(line)
                va[date.fromisoformat(o["date"])] = value_area({int(k): v for k, v in o["bins"].items()})
        self.va = va

    def sma(self, k: int, n: int) -> float | None:         # 날짜 k까지 포함
        return sum(self.cl[k - n + 1:k + 1]) / n if k + 1 >= n else None


def simulate(D: Data, strat, start: date, end: date, slip: float) -> dict:  # type: ignore[no-untyped-def]
    cash, qty, entry, stop, target = 10000.0, 0.0, 0.0, None, None
    pend = None
    trades, curve = [], []
    entry_t = None
    st_ = {}
    for i, (t, o, h, l, c, _) in enumerate(D.hours):
        if not (start <= t.date() <= end):
            continue
        if pend is not None:
            kind, meta = pend
            if kind == "buy" and qty == 0:
                px = o * (1 + slip)
                if meta.get("max_px") is None or px < meta["max_px"]:
                    w = meta["w"](px) if callable(meta["w"]) else meta["w"]
                    q = math.floor(cash * w / (px * (1 + FEE)) / STEP) * STEP
                    if q > 0:
                        cash -= q * px * (1 + FEE)
                        qty, entry, entry_t = q, px, t
                        stop = meta["stop"](px) if callable(meta.get("stop")) else meta.get("stop")
                        target = meta.get("target")
            elif kind == "sell" and qty > 0:
                px = o * (1 - slip)
                cash += qty * px * (1 - FEE)
                trades.append((str(entry_t), str(t), entry, px, qty, meta))
                qty = 0.0
            pend = None
        if qty > 0 and (stop is not None or target is not None):
            fill = why = None
            if stop is not None and l <= stop:
                fill, why = (min(o, stop)) * (1 - slip), "stop"
            elif target is not None and h >= target:
                fill, why = max(o, target), "target"
            if fill is not None:
                cash += qty * fill * (1 - FEE)
                trades.append((str(entry_t), str(t), entry, fill, qty, why))
                qty, stop, target = 0.0, None, None
        act = strat(D, i, t, c, qty > 0, st_, entry)
        if act is not None:
            pend = act
        curve.append((t, cash + qty * c))
    peak, mdd = 0.0, 0.0
    for _, v in curve:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    ret = curve[-1][1] / 10000 - 1
    yrs = (end - start).days / 365.25
    cagr = (1 + ret) ** (1 / yrs) - 1
    pnl = [q * (x * (1 - FEE) - e * (1 + FEE)) for _, _, e, x, q, _ in trades]
    daily = {}
    for tt, v in curve:
        daily[tt.date()] = v
    return {"ret": ret, "mdd": mdd, "ratio": cagr / mdd if mdd else float("inf"), "trades": len(trades),
            "ev": st.fmean(pnl) if pnl else 0.0, "ev_pct": st.fmean([x * (1 - FEE) / (e * (1 + FEE)) - 1 for _, _, e, x, _, _ in trades]) if trades else 0.0,
            "win": sum(1 for p in pnl if p > 0) / len(pnl) if pnl else 0.0, "daily": daily, "trade_list": trades}


def buy_hold(D: Data, start: date, end: date) -> dict:
    hs = [h for h in D.hours if start <= h[0].date() <= end]
    q = 1 / (hs[0][1] * 1.0005 * (1 + FEE))
    peak, mdd = 0.0, 0.0
    for h in hs:
        v = q * h[4]
        peak, mdd = max(peak, v), max(mdd, (max(peak, v) - v) / max(peak, v))
    ret = q * hs[-1][4] - 1
    cagr = (1 + ret) ** (365.25 / (end - start).days) - 1
    return {"ret": ret, "mdd": mdd, "ratio": cagr / mdd}


# ---- (a) v1: 일봉(23시 봉 종가) / 1시간 판정판 ----
def v1(hourly: bool, entry_n: int = 25, exit_n: int = 50, stop_atr: float = 2.0, risk: float = 0.05, maxw: float = 0.98):  # type: ignore[no-untyped-def]
    def f(D: Data, i: int, t: datetime, c: float, holding: bool, s: dict, entry: float):  # type: ignore[no-untyped-def]
        k = D.di[t.date()]
        if not hourly and t.hour != 23:
            return None
        if hourly:                                  # 완료된 일봉만(오늘 제외)
            kk = k - 1
            if kk < max(entry_n, exit_n, 15):
                return None
            hi25 = max(D.cl[kk - entry_n + 1:kk + 1])
            sma = D.sma(kk, exit_n)
            atr = D.atr[kk]
        else:                                       # 23시 종가 = 오늘 일봉 종가(v1과 같음)
            if k < max(entry_n, exit_n, 15):
                return None
            hi25 = max(D.cl[k - entry_n:k])
            sma = D.sma(k, exit_n)
            atr = D.atr[k]
        if atr is None:
            return None
        if holding:
            if c < s["stop"]:
                return ("sell", "stop_close")
            if c < sma:
                return ("sell", "sma")
            return None
        if c > hi25:
            s["atr0"] = atr
            def stopset(px: float, a: float = atr) -> float:
                s["stop"] = px - stop_atr * a
                return None  # type: ignore[return-value]
            return ("buy", {"w": lambda px, a=atr: min(maxw, risk / (stop_atr * a / px)), "stop": stopset})
        return None
    return f


# ---- (b) 변동성 돌파 ----
def vb(k_mult: float, trend: bool):  # type: ignore[no-untyped-def]
    def f(D: Data, i: int, t: datetime, c: float, holding: bool, s: dict, entry: float):  # type: ignore[no-untyped-def]
        k = D.di[t.date()]
        if holding:
            return ("sell", "next_open") if t.hour == 23 else None
        if k < 21 or s.get("day") == t.date() or t.hour == 23:
            return None
        if trend and not (D.cl[k - 1] > D.sma(k - 1, 20)):
            return None
        tgt = D.d[k][0] + k_mult * (D.d[k - 1][1] - D.d[k - 1][2])
        if c >= tgt:
            s["day"] = t.date()
            return ("buy", {"w": 0.98})
        return None
    return f


# ---- (c) 볼륨 프로파일 80% 규칙(롱만) ----
def vp80(m: int):  # type: ignore[no-untyped-def]
    def f(D: Data, i: int, t: datetime, c: float, holding: bool, s: dict, entry: float):  # type: ignore[no-untyped-def]
        d = t.date()
        k = D.di[d]
        if holding:
            return ("sell", "day_end") if t.hour == 23 else None
        if s.get("cur") != d:
            s.update(cur=d, cnt=0, low=float("inf"), done=False)
        s["low"] = min(s["low"], D.hours[i][3])
        if s["done"] or k < 1 or D.dates[k - 1] not in D.va or t.hour == 23:
            return None
        val, vah = D.va[D.dates[k - 1]]
        if not D.d[k][0] < val:
            return None
        s["cnt"] = s["cnt"] + 1 if val <= c <= vah else 0
        if s["cnt"] >= m:
            s["done"] = True
            return ("buy", {"w": 0.98, "stop": s["low"], "target": vah, "max_px": vah})
        return None
    return f


def claim_check(D: Data, start: date, end: date) -> dict:
    """글의 '80%' 확인: 시가가 전날 가치 구간 밖 → 1시간 종가가 안으로 → 그 뒤 그날 안에 반대편 끝 도달 비율."""
    out = {"long": [0, 0], "short": [0, 0]}
    byday = defaultdict(list)
    for h in D.hours:
        if start <= h[0].date() <= end:
            byday[h[0].date()].append(h)
    for d, hs in byday.items():
        k = D.di[d]
        if k < 1 or D.dates[k - 1] not in D.va:
            continue
        val, vah = D.va[D.dates[k - 1]]
        o = hs[0][1]
        for j, h in enumerate(hs[:-1]):
            if val <= h[4] <= vah:
                rest = hs[j + 1:]
                if o < val:
                    out["long"][0] += 1
                    out["long"][1] += any(x[2] >= vah for x in rest)
                elif o > vah:
                    out["short"][0] += 1
                    out["short"][1] += any(x[3] <= val for x in rest)
                break
    return out


def corr(a: dict, b: dict) -> float:
    ds = sorted(set(a) & set(b))
    ra = [a[y] / a[x] - 1 for x, y in zip(ds, ds[1:])]
    rb = [b[y] / b[x] - 1 for x, y in zip(ds, ds[1:])]
    ma, mb = st.fmean(ra), st.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float("nan")


def line(name: str, r: dict) -> str:
    return (f"  {name:28s} 수익 {r['ret']:+8.0%} MDD {r['mdd']:5.1%} 비율 {r['ratio']:5.2f} 거래 {r['trades']:4d} "
            f"승률 {r['win']:.0%} 거래당 {r['ev_pct']:+.2%}")


def main() -> int:
    D = Data()
    print(f"1시간 봉 {len(D.hours)} · 일봉 {len(D.dates)} · 판정 아님 · 비율 = 연 수익/MDD")
    out: dict = {}
    per = {"학습": TRAIN, "확인": CONF, "전체": FULL}
    for pn, (s, e) in per.items():
        bh = buy_hold(D, s, e)
        print(f"\n[{pn} {s}~{e}] 그냥 보유 수익 {bh['ret']:+.0%} MDD {bh['mdd']:.1%} 비율 {bh['ratio']:.2f}")
        out[pn] = {"bh": bh}
        runs = {"v1 일봉(23시 판정)": v1(False), "(a) v1 1시간 판정": v1(True)}
        for km in (0.4, 0.5, 0.6):
            for tr in (False, True):
                runs[f"(b) 변동성 돌파 k{km}{' 추세' if tr else ''}"] = vb(km, tr)
        for m in (1, 2):
            runs[f"(c) VP 80% m{m}"] = vp80(m)
        for name, fn in runs.items():
            r = simulate(D, fn, s, e, 0.0005)
            r2 = simulate(D, fn, s, e, 0.001)
            r4 = simulate(D, fn, s, e, 0.002)
            out[pn][name] = {k: v for k, v in r.items() if k not in ("daily", "trade_list")} | {
                "ev_pct_slip01": r2["ev_pct"], "ev_pct_slip02": r4["ev_pct"], "daily": {str(k): v for k, v in r["daily"].items()}}
            print(line(name, r) + f" | 슬리피지 0.1% {r2['ev_pct']:+.2%} · 0.2% {r4['ev_pct']:+.2%}")
        cc = claim_check(D, s, e)
        out[pn]["claim"] = cc
        print(f"  80% 주장 확인: 롱 셋업 {cc['long'][0]}회 중 VAH 도달 {cc['long'][1] / max(cc['long'][0], 1):.0%} · "
              f"숏 셋업 {cc['short'][0]}회 중 VAL 도달 {cc['short'][1] / max(cc['short'][0], 1):.0%}")
    # ---- 사전 기준 ----
    print("\n사전 기준 대조")
    T, C = out["학습"], out["확인"]
    a, base = "(a) v1 1시간 판정", "v1 일봉(23시 판정)"
    ok_a = T[a]["ratio"] >= T[base]["ratio"] and C[a]["ratio"] >= C[base]["ratio"] and out["전체"][a]["trades"] >= 1.5 * out["전체"][base]["trades"]
    print(f"  (a): 학습 {T[a]['ratio']:.2f} vs {T[base]['ratio']:.2f}, 확인 {C[a]['ratio']:.2f} vs {C[base]['ratio']:.2f}, 거래 {out['전체'][a]['trades']} vs {out['전체'][base]['trades']} → {'v1 장중판 후보(가설)' if ok_a else '폐기'}")
    bs = [n for n in T if n.startswith("(b)")]
    b = max(bs, key=lambda n: T[n]["ratio"])
    ok_b = all(X[b]["ev_pct_slip02"] > 0 and X[b]["ratio"] > X["bh"]["ratio"] for X in (T, C))
    cb = corr({date.fromisoformat(k): v for k, v in out["전체"][b]["daily"].items()}, {date.fromisoformat(k): v for k, v in out["전체"][base]["daily"].items()})
    print(f"  (b): 학습 선택 {b} — 슬리피지 0.2% 거래당 학습 {T[b]['ev_pct_slip02']:+.2%} 확인 {C[b]['ev_pct_slip02']:+.2%}, 비율 학습 {T[b]['ratio']:.2f}(보유 {T['bh']['ratio']:.2f}) 확인 {C[b]['ratio']:.2f}(보유 {C['bh']['ratio']:.2f}) → {'후보(가설)' if ok_b else '폐기'} · v1과 일별 상관 {cb:+.2f}")
    cs_ = [n for n in T if n.startswith("(c)")]
    c = max(cs_, key=lambda n: T[n]["ratio"])
    ok_c = T[c]["ev_pct_slip01"] > 0 and C[c]["ev_pct_slip01"] > 0 and out["전체"][c]["trades"] >= 30
    print(f"  (c): 학습 선택 {c} — 슬리피지 0.1% 거래당 학습 {T[c]['ev_pct_slip01']:+.2%} 확인 {C[c]['ev_pct_slip01']:+.2%}, 전체 거래 {out['전체'][c]['trades']} → {'후보(가설)' if ok_c else '폐기'}")
    out["verdict"] = {"a": ok_a, "b": [b, ok_b, cb], "c": [c, ok_c]}
    for pn in per:
        for n in list(out[pn]):
            if isinstance(out[pn][n], dict):
                out[pn][n].pop("daily", None)
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-intraday.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"저장: {f.relative_to(LAB)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

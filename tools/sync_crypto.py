"""운영 바이낸스 공개 시세 사본 → 전략실 data/crypto (읽기만, 2025-12-31까지 — 2026 이후는 최종 확인 구간 D-163).

  python tools/sync_crypto.py --symbol ETHUSDT [--src <운영 폴더>] [--hourly]
  1d → data/crypto/<심볼>-1d.csv (date,open,high,low,close,volume,quote_volume)
  --hourly: 1m → data/crypto/<심볼>-1h.csv (time,open,high,low,close,volume,minutes) — UTC 시각별 묶음, 빈 분은 건너뜀
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SRC = Path(r"C:\AI\trading_system\trading_system\var\backtest\data\binance-public-20261017")
CUT = "2026-01-01"


def daily(src: Path, sym: str) -> int:
    out = LAB / "data" / "crypto" / f"{sym}-1d.csv"
    n = 0
    with (src / f"{sym}-1d.csv").open(encoding="utf-8") as f, out.open("w", newline="", encoding="utf-8") as g:
        w = csv.writer(g)
        w.writerow(["date", "open", "high", "low", "close", "volume", "quote_volume"])
        for r in csv.DictReader(f):
            d = r["open_time_utc"][:10]
            if d >= CUT:
                break
            w.writerow([d, r["open"], r["high"], r["low"], r["close"], r["volume"], r["quote_volume"]])
            n += 1
    return n


def hourly(src: Path, sym: str) -> int:
    out = LAB / "data" / "crypto" / f"{sym}-1h.csv"
    n, cur = 0, None
    with (src / f"{sym}-1m.csv").open(encoding="utf-8") as f, out.open("w", newline="", encoding="utf-8") as g:
        w = csv.writer(g)
        w.writerow(["time", "open", "high", "low", "close", "volume", "minutes"])
        for r in csv.DictReader(f):
            t = r["open_time_utc"][:13]
            if t[:10] >= CUT:
                break
            o, h, l, c, v = (float(r[k]) for k in ("open", "high", "low", "close", "volume"))
            if cur is None or cur[0] != t:
                if cur is not None:
                    w.writerow([cur[0] + ":00", cur[1], cur[2], cur[3], cur[4], round(cur[5], 8), cur[6]])
                    n += 1
                cur = [t, o, h, l, c, v, 1]
            else:
                cur[2], cur[3], cur[4], cur[5], cur[6] = max(cur[2], h), min(cur[3], l), c, cur[5] + v, cur[6] + 1
        if cur is not None:
            w.writerow([cur[0] + ":00", cur[1], cur[2], cur[3], cur[4], round(cur[5], 8), cur[6]])
            n += 1
    return n


def minutes_bars(src: Path, sym: str, m: int) -> int:
    """1m → m분 봉(data/crypto/<심볼>-<m>m.csv, time = 봉 시작 UTC). 1시간(--hourly)과 같은 방식."""
    out = LAB / "data" / "crypto" / f"{sym}-{m}m.csv"
    n, cur = 0, None
    with (src / f"{sym}-1m.csv").open(encoding="utf-8") as f, out.open("w", newline="", encoding="utf-8") as g:
        w = csv.writer(g)
        w.writerow(["time", "open", "high", "low", "close", "volume", "minutes"])
        for r in csv.DictReader(f):
            ts = r["open_time_utc"]
            if ts[:10] >= CUT:
                break
            t = f"{ts[:14]}{int(ts[14:16]) // m * m:02d}"
            o, h, l, c, v = (float(r[k]) for k in ("open", "high", "low", "close", "volume"))
            if cur is None or cur[0] != t:
                if cur is not None:
                    w.writerow([cur[0], cur[1], cur[2], cur[3], cur[4], round(cur[5], 8), cur[6]])
                    n += 1
                cur = [t, o, h, l, c, v, 1]
            else:
                cur[2], cur[3], cur[4], cur[5], cur[6] = max(cur[2], h), min(cur[3], l), c, cur[5] + v, cur[6] + 1
        if cur is not None:
            w.writerow([cur[0], cur[1], cur[2], cur[3], cur[4], round(cur[5], 8), cur[6]])
            n += 1
    return n


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--hourly", action="store_true")
    ap.add_argument("--minutes", type=int, default=0, help="m분 봉도 만듦(예: 15, 60 미만 약수)")
    ns = ap.parse_args(argv)
    src = Path(ns.src)
    nd = daily(src, ns.symbol)
    msg = f"{ns.symbol}: 일봉 {nd}"
    if ns.hourly:
        msg += f" · 1시간 {hourly(src, ns.symbol)}"
    if ns.minutes:
        msg += f" · {ns.minutes}분 {minutes_bars(src, ns.symbol, ns.minutes)}"
    with (LAB / "data" / "crypto" / "SOURCE.txt").open("a", encoding="utf-8") as f:
        f.write(f"source={src / (ns.symbol + '-1d.csv')}{' + 1m→1h' if ns.hourly else ''} · cutoff={CUT} · {msg} (tools/sync_crypto.py)\n")
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

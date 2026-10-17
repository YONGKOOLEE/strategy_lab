"""사용자 매매 내역(peak·momentum) 분석 — 매수·매도 시점의 차트·거래량 특징을 계산해 공통 타점·청산 기준을 추정한다(전략 아님).

입력: data/user-trades/<이름>.xlsx (git 제외. 열: 빈칸, buydate, 종목명, buyprice, selldate, sellprice, holding period, P&L).
  ※ 모든 행에서 buydate > selldate → 날짜 열 이름이 뒤바뀐 것으로 보고 **이른 날짜 = 매수일**로 쓴다(가격 열은 P&L과 일치).
일봉: --daily 폴더의 <코드>.csv(date,open,high,low,close,volume, 수정주가). 종목명→코드: --names CSV(code,name).
  2026년 거래 포함(사용자 결정 2026-10-16) — 2026은 운영 최종 확인 구간(D-163). 여기서 나온 규칙은 2026 최종 확인으로 검증할 수 없다.
출력: results/user-trades/<이름>-features.csv(거래별 특징), 표준출력 요약(매수일 특징 분포 vs 같은 종목 기준선).
표준 라이브러리만. 실행: python research/user_trades_analysis.py --daily <폴더> --names <csv> [--trades peak momentum]
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics as st
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


# --- xlsx (표준 라이브러리) ----------------------------------------------------------------------

def read_xlsx_rows(path: Path) -> list[list[str]]:
    z = zipfile.ZipFile(path)
    shared = ["".join(t.text or "" for t in si.iter(NS + "t"))
              for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(NS + "si")] if "xl/sharedStrings.xml" in z.namelist() else []
    rows = []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(NS + "row"):
        cells = {}
        for c in row.findall(NS + "c"):
            ref = "".join(ch for ch in c.get("r") if ch.isalpha())
            col = 0
            for ch in ref:
                col = col * 26 + ord(ch) - 64
            v = c.find(NS + "v")
            cells[col - 1] = (shared[int(v.text)] if c.get("t") == "s" else v.text) if v is not None else ""
        if cells:
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return rows


def load_trades(path: Path) -> list[dict]:
    xl = lambda s: date(1899, 12, 30) + timedelta(days=int(float(s)))  # noqa: E731
    out = []
    for r in read_xlsx_rows(path)[1:]:
        try:
            d1, d2 = xl(r[1]), xl(r[4])
            out.append({"name": r[2], "buy": min(d1, d2), "sell": max(d1, d2), "bp": float(r[3]), "sp": float(r[5]),
                        "hold": int(str(r[6]).rstrip("일")), "pl": float(r[7])})
        except (ValueError, IndexError):
            continue
    return out


def load_daily(path: Path) -> list[tuple[date, float, float, float, float, float]]:
    with path.open(encoding="utf-8") as f:
        return [(date.fromisoformat(r["date"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                 float(r["volume"])) for r in csv.DictReader(f)]


# --- 특징 ------------------------------------------------------------------------------------------

def sma(xs: list[float], n: int) -> float | None:
    return sum(xs[-n:]) / n if len(xs) >= n else None


def features(bars: list, i: int) -> dict | None:
    """i = 매수일 봉 인덱스. 판단 기준은 전일(i-1)까지 확정 정보 + 매수일 봉(체결 위치 확인용)."""
    if i < 130:
        return None
    c = [b[4] for b in bars[:i]]          # 전일까지 종가
    v = [b[5] for b in bars[:i]]
    hi = [b[2] for b in bars[:i]]
    prev = c[-1]
    w = min(250, len(c))
    h52c, h52h = max(c[-w:]), max(hi[-w:])
    low126 = min(c[-126:])
    i_h = len(c) - 1 - c[::-1].index(max(c[-60:]))   # 최근 60일 최고 종가 위치
    f = {
        "prev_vs_h52c": prev / h52c - 1,                       # 전일 종가의 52주 최고 종가 대비
        "day_high_vs_h52": bars[i][2] / h52h - 1,              # 매수일 고가가 직전 52주 최고가 넘었나
        "ret5": prev / c[-6] - 1, "ret20": prev / c[-21] - 1, "ret60": prev / c[-61] - 1, "ret120": prev / c[-121] - 1,
        "adv_from_126low": prev / low126 - 1,
        "days_since_60h": len(c) - 1 - i_h, "dd_from_60h": prev / c[i_h] - 1,
        "vol_prev_x50": v[-1] / (sum(v[-51:-1]) / 50) if sum(v[-51:-1]) > 0 else None,
        "vol_day_x50": bars[i][5] / (sum(v[-50:]) / 50) if sum(v[-50:]) > 0 else None,
        "gap_open": bars[i][1] / prev - 1,
        "day_ret": bars[i][4] / prev - 1,
    }
    s5, s20, s60, s120 = (sma(c, n) for n in (5, 20, 60, 120))
    f["align_5_20_60_120"] = int(None not in (s5, s20, s60, s120) and prev > s5 > s20 > s60 > s120)  # type: ignore[operator]
    f["above_sma20"] = int(s20 is not None and prev > s20)
    f["above_sma60"] = int(s60 is not None and prev > s60)
    return f


def entry_fill(bar: tuple, price: float) -> str:
    _, o, h, l, cl, _ = bar
    tol = 0.003
    if abs(price / o - 1) <= tol:
        return "시가"
    if abs(price / cl - 1) <= tol:
        return "종가"
    if l * (1 - tol) <= price <= h * (1 + tol):
        return "장중"
    return "범위밖"


def summarize(name: str, rows: list[dict], base: list[dict]) -> None:
    keys = [k for k in rows[0] if k not in ("name", "code", "buy", "sell", "pl", "hold", "fill", "exit_fill", "exit_vs_entry", "winner")]
    print(f"\n== {name}: 매수일 특징 (거래 {len(rows)}건 vs 같은 종목·같은 기간 무작위 날 {len(base)}개) — 중앙 [사분위]")
    for k in keys:
        a = [r[k] for r in rows if r.get(k) is not None]
        b = [r[k] for r in base if r.get(k) is not None]
        if not a or not b:
            continue
        qa = statistics_q(a)
        qb = statistics_q(b)
        print(f"  {k:<20} 거래 {qa}   | 기준선 {qb}")
    for grp, sel in (("이익", [r for r in rows if r["pl"] > 0]), ("손실", [r for r in rows if r["pl"] <= 0])):
        print(f"  [{grp} {len(sel)}건] " + " ".join(f"{k} {st.median([r[k] for r in sel if r.get(k) is not None]):.3g}"
                                                  for k in ("prev_vs_h52c", "ret20", "ret60", "adv_from_126low", "vol_prev_x50", "gap_open") if sel))
    from collections import Counter
    print("  매수 체결 위치:", dict(Counter(r["fill"] for r in rows)), " 매도 체결 위치:", dict(Counter(r["exit_fill"] for r in rows)))


def statistics_q(xs: list[float]) -> str:
    xs = sorted(xs)
    q = lambda p: xs[int(p * (len(xs) - 1))]  # noqa: E731
    fmt = (lambda x: f"{x:+.1%}") if max(abs(x) for x in xs) < 5 and any(abs(x) < 1 and x != int(x) for x in xs) else (lambda x: f"{x:.2f}")
    return f"{fmt(q(.5))} [{fmt(q(.25))}, {fmt(q(.75))}]"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", required=True)
    ap.add_argument("--names", required=True)
    ap.add_argument("--trades", nargs="+", default=["peak", "momentum"])
    ap.add_argument("--seed", type=int, default=7)
    ns = ap.parse_args(argv)
    daily = Path(ns.daily)
    with open(ns.names, encoding="utf-8") as f:
        names = {r["name"]: r["code"] for r in csv.DictReader(f)}
    out_dir = LAB / "results" / "user-trades"
    out_dir.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(ns.seed)
    cache: dict[str, list] = {}
    missing: dict[str, set[str]] = {}
    for tname in ns.trades:
        trades = load_trades(LAB / "data" / "user-trades" / f"{tname}.xlsx")
        rows, base = [], []
        for t in trades:
            code = names.get(t["name"])
            path = daily / f"{code}.csv" if code else None
            if not path or not path.exists():
                missing.setdefault(tname, set()).add(t["name"])
                continue
            bars = cache.setdefault(code, load_daily(path))
            idx = {b[0]: k for k, b in enumerate(bars)}
            i, j = idx.get(t["buy"]), idx.get(t["sell"])
            if i is None:
                missing.setdefault(tname + "(날짜 없음)", set()).add(t["name"])
                continue
            f = features(bars, i)
            if f is None:
                continue
            f.update(name=t["name"], code=code, buy=t["buy"], sell=t["sell"], pl=t["pl"], hold=t["hold"],
                     fill=entry_fill(bars[i], t["bp"]), exit_fill=entry_fill(bars[j], t["sp"]) if j is not None else "날짜 없음")
            rows.append(f)
            for _ in range(5):   # 기준선: 같은 종목, 거래 기간(첫 매수~마지막 매수) 안 무작위 날
                k = rnd.randrange(max(130, i - 120), min(len(bars) - 1, i + 120) + 1)
                g = features(bars, k)
                if g:
                    base.append(g)
        if rows:
            with (out_dir / f"{tname}-features.csv").open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            summarize(tname, rows, base)
    for k, v in missing.items():
        (out_dir / f"missing-{k}.txt").write_text("\n".join(sorted(v)), encoding="utf-8")
        print(f"\n데이터 없음 {k}: {len(v)}종목 → results/user-trades/missing-{k}.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

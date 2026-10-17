"""사용자 매매 내역 — 후보 매수 신호·청산 규칙의 일치율 검사(user_trades_analysis.py의 다음 단계, 전략 아님).

- 매수: 매수일(종가 체결 기준) 봉에서 후보 신호가 참인 비율 vs 같은 종목 무작위 날(기준선). 비율 차이가 큰 신호가 실제 조건 후보.
- 청산: 후보 규칙을 매수 다음 봉부터 적용했을 때 **처음 발동한 날 = 실제 매도일** 비율(이익·손실 따로), 먼저 발동 비율.
실행: python research/user_trades_rules.py --daily <폴더> --names <csv>
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from user_trades_analysis import LAB, load_daily, load_trades  # noqa: E402


def sma(c: list[float], k: int, n: int) -> float | None:
    return sum(c[k - n + 1:k + 1]) / n if k + 1 >= n else None


def atr(b: list, k: int, n: int = 14) -> float | None:
    if k < n:
        return None
    return sum(max(b[j][2] - b[j][3], abs(b[j][2] - b[j - 1][4]), abs(b[j][3] - b[j - 1][4])) for j in range(k - n + 1, k + 1)) / n


def entry_signals(b: list, k: int) -> dict[str, bool] | None:
    """k일 종가 기준(매수일 당일 봉). 당일 종가 매수라 당일 봉까지 본다."""
    if k < 260:
        return None
    c = [x[4] for x in b]
    v = [x[5] for x in b]
    s = {n: sma(c, k, n) for n in (5, 10, 20, 60, 120)}
    sp = {n: sma(c, k - 1, n) for n in (5, 20, 60)}
    v50 = sum(v[k - 50:k]) / 50
    return {
        "52주 종가 신고가": c[k] > max(c[k - 250:k]),
        "60일 종가 신고가": c[k] > max(c[k - 60:k]),
        "20일 종가 신고가": c[k] > max(c[k - 20:k]),
        "10일 종가 신고가": c[k] > max(c[k - 10:k]),
        "20일선 상향 돌파(당일)": c[k] > s[20] and c[k - 1] <= sp[20],
        "60일선 상향 돌파(당일)": c[k] > s[60] and c[k - 1] <= sp[60],
        "5일선>20일선 골든크로스(당일)": s[5] > s[20] and sp[5] <= sp[20],
        "5일선>20일선 골든크로스(5일 안)": any(sma(c, j, 5) > sma(c, j, 20) and sma(c, j - 1, 5) <= sma(c, j - 1, 20) for j in range(k - 4, k + 1)),
        "종가>20일선": c[k] > s[20],
        "종가>60일선": c[k] > s[60],
        "20일선>60일선": s[20] > s[60],
        "60일선>120일선": s[60] > s[120],
        "당일 +3% 이상": c[k] / c[k - 1] - 1 >= 0.03,
        "당일 +5% 이상": c[k] / c[k - 1] - 1 >= 0.05,
        "당일 거래량 1.5배↑": v[k] >= 1.5 * v50,
        "당일 거래량 2배↑": v[k] >= 2 * v50,
        "양봉(종가>시가)": c[k] > b[k][1],
    }


def exit_rules(b: list, i: int, bp: float):
    c = [x[4] for x in b]
    a0 = atr(b, i) or 0
    ent_low = b[i][3]
    rules = {
        "장중 −8%": lambda k, pk, ph: b[k][3] <= bp * 0.92,
        "종가 −8%": lambda k, pk, ph: c[k] <= bp * 0.92,
        "종가<SMA5": lambda k, pk, ph: c[k] < sma(c, k, 5),
        "종가<SMA10": lambda k, pk, ph: c[k] < sma(c, k, 10),
        "종가<SMA20": lambda k, pk, ph: c[k] < sma(c, k, 20),
        "SMA5<SMA20 데드크로스": lambda k, pk, ph: sma(c, k, 5) < sma(c, k, 20) and sma(c, k - 1, 5) >= sma(c, k - 1, 20),
        "종가<매수일 저가": lambda k, pk, ph: c[k] < ent_low,
        "장중<매수일 저가": lambda k, pk, ph: b[k][3] < ent_low,
        "종가<전일 저가": lambda k, pk, ph: c[k] < b[k - 1][3],
        "종가<매수가(본전)": lambda k, pk, ph: c[k] < bp,
        "종가 고점−8%": lambda k, pk, ph: c[k] <= pk * 0.92,
        "장중 고가고점−8%": lambda k, pk, ph: b[k][3] <= ph * 0.92,
        "장중 고가고점−10%": lambda k, pk, ph: b[k][3] <= ph * 0.90,
        "종가 고점−2ATR": lambda k, pk, ph: c[k] <= pk - 2 * a0,
        "종가 고점−3ATR": lambda k, pk, ph: c[k] <= pk - 3 * a0,
        "종가<10일 최저": lambda k, pk, ph: c[k] < min(c[k - 10:k]),
        "종가<20일 최저": lambda k, pk, ph: c[k] < min(c[k - 20:k]),
        "보유 20봉": lambda k, pk, ph: k - i >= 20,
    }
    return rules


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", required=True)
    ap.add_argument("--names", required=True)
    ap.add_argument("--trades", nargs="+", default=["peak", "momentum"])
    ns = ap.parse_args(argv)
    daily = Path(ns.daily)
    with open(ns.names, encoding="utf-8") as f:
        names = {r["name"]: r["code"] for r in csv.DictReader(f)}
    rnd = random.Random(11)
    cache: dict[str, list] = {}
    lines: list[str] = []
    for tn in ns.trades:
        ent, base, n_ok = {}, {}, 0
        ex = {"W": {}, "L": {}}
        nW = nL = 0
        for t in load_trades(LAB / "data" / "user-trades" / f"{tn}.xlsx"):
            code = names.get(t["name"])
            if not code or not (daily / f"{code}.csv").exists():
                continue
            b = cache.setdefault(code, load_daily(daily / f"{code}.csv"))
            idx = {x[0]: k for k, x in enumerate(b)}
            i, j = idx.get(t["buy"]), idx.get(t["sell"])
            if i is None:
                continue
            e = entry_signals(b, i)
            if e:
                n_ok += 1
                for key, val in e.items():
                    ent[key] = ent.get(key, 0) + int(val)
                for _ in range(5):
                    kk = rnd.randrange(max(260, i - 120), min(len(b) - 1, i + 120) + 1)
                    g = entry_signals(b, kk)
                    if g:
                        base.setdefault("_n", 0)
                        base["_n"] += 1
                        for key, val in g.items():
                            base[key] = base.get(key, 0) + int(val)
            if j is None or j <= i or i < 30:
                continue
            grp = "W" if t["pl"] > 0 else "L"
            nW += grp == "W"
            nL += grp == "L"
            for r, fn in exit_rules(b, i, t["bp"]).items():
                first, pk, ph = None, b[i][4], b[i][2]
                for k in range(i + 1, min(j + 1, len(b) - 1) + 1):
                    if fn(k, pk, ph):
                        first = k
                        break
                    pk, ph = max(pk, b[k][4]), max(ph, b[k][2])
                s = ex[grp].setdefault(r, [0, 0])
                s[0] += first == j
                s[1] += first is not None and first < j
        lines.append(f"\n== {tn}: 매수 신호 (매수일 {n_ok}건 vs 기준선 {base.get('_n', 0)}개) — 참인 비율")
        for key in ent:
            lines.append(f"  {key:<26} 거래 {ent[key] / n_ok:>5.0%}   기준선 {base.get(key, 0) / max(1, base.get('_n', 1)):>5.0%}")
        lines.append(f"== {tn}: 청산 규칙 — 첫 발동일 = 실제 매도일 / 먼저 발동   (이익 {nW}, 손실 {nL})")
        for r in ex["W"]:
            w, l = ex["W"][r], ex["L"].get(r, [0, 0])
            lines.append(f"  {r:<20} 이익 {w[0] / nW:>4.0%} / {w[1] / nW:>4.0%}   손실 {l[0] / nL:>4.0%} / {l[1] / nL:>4.0%}")
    text = "\n".join(lines)
    print(text)
    out = LAB / "results" / "user-trades" / "rules-match.txt"
    out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

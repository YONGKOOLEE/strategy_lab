"""볼륨 프로파일 수용/거부 사건 연구 (판정 아님). 사전 등록 research/2026-10-18-vp-design.md (2026-10-18 00:37).

  python research/btc_vp_study.py build   → 운영 1분봉 사본(읽기) → data/crypto/BTCUSDT-vpbins.jsonl (UTC 날짜별 0.2% 로그 가격 칸 거래량)
  python research/btc_vp_study.py study   → 1단계 사건 연구 표 + 2단계 진행 여부, results/cryptosim/<날짜>-vp-study.json
"""

from __future__ import annotations

import csv
import json
import math
import statistics as st
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SRC = Path(r"C:\AI\trading_system\trading_system\var\backtest\data\binance-public-20261017\BTCUSDT-1m.csv")
BINS = LAB / "data" / "crypto" / "BTCUSDT-vpbins.jsonl"
STEP = math.log(1.002)
END = date(2025, 12, 31)
TRAIN = (date(2017, 10, 1), date(2021, 12, 31))
CONF = (date(2022, 1, 1), date(2025, 12, 31))


def build() -> int:
    days: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    with SRC.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = r["open_time_utc"][:10]
            if d > END.isoformat():
                break
            v = float(r["volume"])
            if v <= 0:
                continue
            p = (float(r["high"]) + float(r["low"]) + float(r["close"])) / 3
            days[d][math.floor(math.log(p) / STEP)] += v
    with BINS.open("w", encoding="utf-8") as f:
        for d in sorted(days):
            f.write(json.dumps({"date": d, "bins": {str(k): round(v, 6) for k, v in days[d].items()}}) + "\n")
    (BINS.parent / "SOURCE-vpbins.txt").write_text(f"{SRC} → {BINS.name}: UTC 날짜별 (고+저+종)/3 가격의 0.2% 로그 칸 거래량, 2025-12-31까지\n",
                                                   encoding="utf-8")
    print(f"{len(days)}일 → {BINS}")
    return 0


def value_area(hist: dict[int, float]) -> tuple[float, float]:
    ks = sorted(hist)
    tot = sum(hist.values())
    i = j = max(range(len(ks)), key=lambda x: hist[ks[x]])
    acc = hist[ks[i]]
    while acc < 0.7 * tot:
        up = hist[ks[j + 1]] if j + 1 < len(ks) else -1.0
        dn = hist[ks[i - 1]] if i > 0 else -1.0
        if up >= dn:
            j += 1
            acc += up
        else:
            i -= 1
            acc += dn
    return math.exp(ks[i] * STEP), math.exp((ks[j] + 1) * STEP)   # VAL = 아래 칸 하단, VAH = 위 칸 상단


def summarize(xs: list[float]) -> dict:
    return {"n": len(xs), "mean": st.fmean(xs) if xs else float("nan"), "median": st.median(xs) if xs else float("nan"),
            "pos": sum(1 for x in xs if x > 0) / len(xs) if xs else float("nan")}


def load_va(N: int) -> dict[str, tuple[float, float]]:
    """날짜 → 직전 N일(그날 제외) 가치 구간 (VAL, VAH)."""
    hist = {}
    with BINS.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            hist[o["date"]] = {int(k): v for k, v in o["bins"].items()}
    ds = sorted(hist)
    out = {}
    for k in range(N, len(ds)):
        h: dict[int, float] = defaultdict(float)
        for w in ds[k - N:k]:
            for b, v in hist[w].items():
                h[b] += v
        out[ds[k]] = value_area(h)
    return out


def stage2(N: int = 50) -> int:
    sys.path.insert(0, str(LAB / "tools"))
    import cryptosim as cs
    va = load_va(N)
    rows = cs.load_csv(LAB / "data" / "crypto" / "BTCUSDT-1d.csv")
    allow = {str(rows[k][0]) for k in range(1, len(rows))
             if str(rows[k][0]) in va and str(rows[k - 1][0]) in va
             and rows[k][4] > va[str(rows[k][0])][1] and rows[k - 1][4] > va[str(rows[k - 1][0])][1]}
    V1 = dict(entry_rule="breakout", entry_n=25, exit_mode="sma", exit_n=50, stop_mode="atr", stop_atr=2.0, stop_when="close",
              risk_ratio=0.05, max_weight=0.98)
    res = {}
    print(f"2단계 — v1 vs v1 + 수용 필터(N={N}, 종가가 이틀 연속 직전 {N}일 VAH 위) · UTC 00시 · 판정 아님")
    for pname, (s, e) in (("학습", (date(2017, 9, 1), TRAIN[1])), ("확인", CONF), ("전체", (date(2017, 9, 1), END))):
        for lab, extra in (("v1", {}), ("v1+수용", {"entry_allow": allow})):
            r = cs.simulate(rows, dict(cs.DEFAULTS, **V1, **extra), s, e)
            cagr = (1 + r["ret"]) ** (365.25 / ((e - s).days + 1)) - 1
            fee = 0.001
            pnl = [q * (x * (1 - fee) - en * (1 + fee)) for _, _, en, x, q, _ in r["trade_list"]]
            res[f"{pname}-{lab}"] = {"ret": r["ret"], "mdd": r["mdd"], "ratio": cagr / r["mdd"], "trades": r["trades"],
                                    "ev": sum(pnl) / len(pnl) if pnl else 0.0, "entries": [t[0] for t in r["trade_list"]]}
            x = res[f"{pname}-{lab}"]
            print(f"  {pname} {lab:7s} 수익 {x['ret']:+8.0%} MDD {x['mdd']:5.1%} 비율 {x['ratio']:.2f} 거래 {x['trades']:2d} 거래당 {x['ev']:+9.0f}")
    ok = all(res[f"{p}-v1+수용"]["ratio"] > res[f"{p}-v1"]["ratio"] for p in ("학습", "확인")) and \
        all(res[f"{p}-v1+수용"]["trades"] >= 0.7 * res[f"{p}-v1"]["trades"] for p in ("학습", "확인"))
    same = all(res[f"{p}-v1+수용"]["entries"] == res[f"{p}-v1"]["entries"] for p in ("학습", "확인"))
    print(f"\n사전 기준: {'결과 동일 — 시험 안 된 것' if same else ('v1 변형 후보(가설)' if ok else '폐기')}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-vp-stage2.json"
    f.write_text(json.dumps({"N": N, "res": res, "verdict": "same" if same else "candidate" if ok else "discard"}, ensure_ascii=False, indent=1),
                 encoding="utf-8")
    return 0


def study() -> int:
    hist = {}
    with BINS.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            hist[o["date"]] = {int(k): v for k, v in o["bins"].items()}
    with (LAB / "data" / "crypto" / "BTCUSDT-1d.csv").open(encoding="utf-8") as f:
        rows = [(r["date"], float(r["open"]), float(r["close"])) for r in csv.DictReader(f)]
    idx = {d: k for k, (d, _, _) in enumerate(rows)}
    out: dict = {}
    for N in (20, 50):
        va: dict[int, tuple[float, float]] = {}
        for k in range(N, len(rows)):
            win = [rows[k - m][0] for m in range(1, N + 1)]
            if not all(w in hist for w in win):
                continue
            h: dict[int, float] = defaultdict(float)
            for w in win:
                for b, v in hist[w].items():
                    h[b] += v
            va[k] = value_area(h)
        res: dict = {}
        for pname, (s, e) in (("학습", TRAIN), ("확인", CONF)):
            ks = [k for k in va if s.isoformat() <= rows[k][0] <= e.isoformat()]
            for hz in (5, 20):
                fwd = lambda k, lag=1: (rows[k + lag - 1 + hz][2] / rows[k + lag][1] - 1) if k + lag - 1 + hz < len(rows) else None  # noqa: E731
                groups: dict[str, list[float]] = defaultdict(list)
                for k in ks:
                    f1 = fwd(k)
                    if f1 is None:
                        continue
                    val, vah = va[k]
                    c = rows[k][2]
                    groups["기준선"].append(f1)
                    groups["위" if c > vah else "아래" if c < val else "안"].append(f1)
                    if c > vah and k - 1 in va and rows[k - 1][2] <= va[k - 1][1] and k + 1 < len(rows):
                        f2 = fwd(k, 2)
                        if f2 is not None:
                            groups["수용" if rows[k + 1][2] > vah else "거부"].append(f2)
                res[f"{pname}-{hz}"] = {g: summarize(v) for g, v in groups.items()}
        out[N] = res
    print("볼륨 프로파일 사건 연구 — BTC UTC 일봉, 직전 N일 가치 구간(70%) · 앞으로 수익 평균/중앙/양수 비율(건수) · 판정 아님, 구간 겹침(건수 과대)")
    for N, res in out.items():
        print(f"\n[N={N}]")
        for key, groups in res.items():
            print(f"  {key}: " + " | ".join(f"{g} {x['mean']:+.1%}/{x['median']:+.1%}/{x['pos']:.0%}({x['n']})"
                                            for g, x in groups.items() if g in ("기준선", "위", "안", "아래", "수용", "거부")))
    passed = []
    for N, res in out.items():
        tr, cf = res["학습-20"], res["확인-20"]
        if "수용" in tr and "거부" in tr and "수용" in cf and "거부" in cf:
            d_tr = tr["수용"]["mean"] - tr["거부"]["mean"]
            d_cf = cf["수용"]["mean"] - cf["거부"]["mean"]
            ok = d_tr >= 0.02 and tr["수용"]["mean"] > tr["기준선"]["mean"] and d_cf > 0
            print(f"\nN={N}: 학습 수용−거부 {d_tr:+.2%}p, 수용 {tr['수용']['mean']:+.2%} vs 기준선 {tr['기준선']['mean']:+.2%}, 확인 수용−거부 {d_cf:+.2%}p → {'통과' if ok else '미달'}")
            if ok:
                passed.append((d_tr, N))
    pick = max(passed)[1] if passed else None
    print(f"\n2단계 진행: {'N=' + str(pick) if pick else '없음 → 카드 폐기(사건 연구 차이 없음)'}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-vp-study.json"
    f.write_text(json.dumps({"events": {str(k): v for k, v in out.items()}, "pick": pick}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(build() if sys.argv[1:] == ["build"] else study() if sys.argv[1:] == ["study"] else stage2() if sys.argv[1:] == ["stage2"] else 2)

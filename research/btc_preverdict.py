"""btc-trend v1 — ① 사전 판정표(C-1~C-8 방식) ③ 위험 5%용 M2 한도 시험. 운영 M2 엔진(tools/m2_quick.run_engine), 판정 아님.

사전 등록: research/2026-10-18-btc-preverdict-design.md (2026-10-18 00:19). 실행: 운영 .venv 파이썬
  python research/btc_preverdict.py verdict   → results/m2/<날짜>-preverdict/verdict.json·표준출력
  python research/btc_preverdict.py limits    → results/m2/<날짜>-limits/limits.json·표준출력
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import m2_quick  # noqa: E402

BASE = {"entry_n": 25, "exit_n": 50, "stop_atr": "2", "risk_ratio": "0.05", "max_weight": "0.98", "order_cap": "1000000000"}
WINDOWS = [(date(y, 1, 1), date(y, 12, 31)) for y in range(2019, 2026)]
VARIANTS = [("entry_n", 20), ("entry_n", 30), ("exit_n", 40), ("exit_n", 60), ("stop_atr", "1.6"), ("stop_atr", "2.4"),
            ("risk_ratio", "0.04"), ("risk_ratio", "0.06"), ("max_weight", "0.784"), ("max_weight", "1.0"),
            ("order_cap", "800000000"), ("order_cap", "1000000000")]   # +20%(1.2e9)는 파라미터 상한 1e9 초과 → 1e9(max_weight와 같은 처리, 00:24 오류로 확인)
SUPPLEMENT = {"보충 위험6%·L1 7%": ({"l1": "0.07"}, {"risk_ratio": "0.06"})}   # 가정 한도 L1 6%가 위험 6%를 막아 변형이 시험되지 않음 — 판정 계산에 넣지 않음


def write_params(folder: Path, name: str, p: dict) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / f"{name}.toml"
    body = "\n".join(f"{k} = {v}" if isinstance(v, int) else f'{k} = "{v}"' for k, v in p.items())
    f.write_text(f'strategy = "btc-trend"\nversion = 1\n\n[params]\n{body}\n', encoding="utf-8")
    return f


def run(out: Path, label: str, params: Path, start: date, end: date, **lim: str) -> dict:
    args = ["--candidate", "btc_trend", "--cls", "BtcTrendV1", "--version", "1", "--params", str(params),
            "--start", start.isoformat(), "--end", end.isoformat(), "--label", label]
    for k, v in lim.items():
        args += [f"--{k}", str(v)]
    ns = m2_quick.parser().parse_args(args)
    res, _, note, _ = m2_quick.run_engine(ns, out / label)
    eq = res.equity
    pnl = [t.pnl for t in res.trades]
    return {"label": label, "start": str(start), "end": str(end), "trades": len(pnl), "pnl_sum": float(sum(pnl, Decimal(0))),
            "ret": float(eq[-1][1] / Decimal(ns.cash) - 1), "mdd": float(res.metrics.get("max_drawdown", "0")),
            "rejects": dict(res.rejects), "k2": res.k2_resumes, "first_entry": str(res.trades[0].entry_day) if res.trades else None,
            "limits": note}


def buy_hold(start: date, end: date, fee: float = 0.001, slip: float = 0.0005) -> tuple[float, float]:
    with (LAB / "data" / "crypto" / "BTCUSDT-1d.csv").open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if start.isoformat() <= r["date"] <= end.isoformat()]
    q = 1 / (float(rows[0]["open"]) * (1 + slip) * (1 + fee))
    peak, mdd = 0.0, 0.0
    for r in rows:
        v = q * float(r["close"])
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    return q * float(rows[-1]["close"]) - 1, mdd


def agg(rs: list[dict]) -> tuple[int, float]:
    n = sum(r["trades"] for r in rs)
    return n, (sum(r["pnl_sum"] for r in rs) / n if n else float("nan"))


def tag(name: str) -> str:
    return name.replace("=", "-").replace("%", "pct")


def verdict() -> int:
    out = LAB / "results" / "m2" / f"{date.today():%Y%m%d}-preverdict"
    pdir = out / "params"
    sets = {"base": ({}, BASE), "slip0.2%": ({"slip": "0.002"}, BASE), "slip0.1%": ({"slip": "0.001"}, BASE)}
    for k, v in VARIANTS:
        sets[f"{k}={v}"] = ({}, dict(BASE, **{k: v}))
    table: dict[str, list[dict]] = {}
    for name, (lim, p) in sets.items():
        f = write_params(pdir, tag(name), p)
        table[name] = [run(out, f"{tag(name)}-{s.year}", f, s, e, **lim) for s, e in WINDOWS]
        n, ev = agg(table[name])
        print(f"{name:22s} 거래 {n:3d} · 거래당 기대값 {ev:+10.2f} USDT · 손실 창 {sum(1 for r in table[name] if r['ret'] < 0)}/7", flush=True)
    for name, (lim, chg) in SUPPLEMENT.items():
        f = write_params(pdir, "supp-risk006", dict(BASE, **chg))
        table[name] = [run(out, f"supp-risk006-l107-{s.year}", f, s, e, **lim) for s, e in WINDOWS]
        n, ev = agg(table[name])
        print(f"{name:22s} 거래 {n:3d} · 거래당 기대값 {ev:+10.2f} USDT · 손실 창 {sum(1 for r in table[name] if r['ret'] < 0)}/7 (판정 계산 제외)", flush=True)
    print("\n창별(base): 연도 · 수익 · MDD · 거래 · 첫 진입 | 그냥 보유 수익·MDD")
    for r in table["base"]:
        s, e = date.fromisoformat(r["start"]), date.fromisoformat(r["end"])
        bh, bm = buy_hold(s, e)
        r["bh_ret"], r["bh_mdd"] = bh, bm
        print(f"  {s.year} {r['ret']:+7.1%} {r['mdd']:6.1%} {r['trades']:2d} {r['first_entry']} | {bh:+7.1%} {bm:6.1%}  거부 {r['rejects']}")
    n, ev = agg(table["base"])
    c2 = n >= 100
    c3 = agg(table["slip0.2%"])[1] > 0
    var = [k for k in table if "=" in k]
    base_sig = [(r["trades"], round(r["pnl_sum"], 6)) for r in table["base"]]
    same = [k for k in var if [(r["trades"], round(r["pnl_sum"], 6)) for r in table[k]] == base_sig]
    c4 = all(agg(table[k])[1] > 0 for k in var)
    loss_w = sum(1 for r in table["base"] if r["ret"] < 0)
    overall = "판단 불가(C-2)" if not c2 else ("통과(과대 추정 가능)" if c3 and c4 else "미충족")
    print(f"\nC-2 거래 {n} ≥ 100? {'충족' if c2 else '판단 불가'} · C-3 슬리피지 0.2% {'충족' if c3 else '미충족'} · "
          f"C-4 ±20% {'충족' if c4 else '미충족'} (결과 동일: {same or '없음'}) · 손실 창 {loss_w}/7 · C-7 과대 추정(사후 선택 자산)")
    print(f"운영 공식 조합: {overall} · C-2 뺀 C-3·C-4: {'충족' if c3 and c4 else '미충족'} · 한도 = 전략실 가정(미승인 한도 가정)")
    (out / "verdict.json").write_text(json.dumps({"table": table, "C2": c2, "C3": c3, "C4": c4, "same": same, "loss_windows": loss_w,
                                                  "overall": overall}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def limits() -> int:
    out = LAB / "results" / "m2" / f"{date.today():%Y%m%d}-limits"
    f = LAB / "candidates" / "btc_trend" / "params-v1.toml"
    s, e = date(2017, 9, 1), date(2025, 12, 31)
    rows = []
    print("1단계: L4 30%(끔), L7 무제한")
    for l1 in ("0.05", "0.055", "0.06"):
        for l23 in ("0.98", "0.99", "1.0"):
            r = run(out, f"s1-l1{l1}-l23{l23}", f, s, e, l1=l1, l2=l23, l3=l23, l4="0.30")
            r.update(l1=l1, l23=l23, l4="0.30")
            rows.append(r)
            print(f"  L1 {l1} L2=L3 {l23}: 거래 {r['trades']} 수익 {r['ret']:+.0%} MDD {r['mdd']:.1%} 거부 {r['rejects']}", flush=True)
    ok = [r for r in rows if not r["rejects"]]
    if not ok:
        print("거부 0 조합 없음 — 2단계 생략")
    else:
        best = min(ok, key=lambda r: (float(r["l1"]), float(r["l23"])))
        print(f"2단계: L1 {best['l1']} L2=L3 {best['l23']} 고정, L4 변화")
        for l4 in ("0.01", "0.02", "0.03", "0.05", "0.10", "0.30"):
            r = run(out, f"s2-l4{l4}", f, s, e, l1=best["l1"], l2=best["l23"], l3=best["l23"], l4=l4)
            r.update(l1=best["l1"], l23=best["l23"], l4=l4)
            rows.append(r)
            print(f"  L4 {l4}: 거래 {r['trades']} 수익 {r['ret']:+.0%} MDD {r['mdd']:.1%} K2 {r['k2']} 거부 {r['rejects']}", flush=True)
    (out / "limits.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(verdict() if sys.argv[1:] == ["verdict"] else limits() if sys.argv[1:] == ["limits"] else 2)

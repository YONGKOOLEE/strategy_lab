"""A. 진입 즉시 청산 금지 수정판(진입에 가격 > SMA(exit_n) 추가) — 일봉판·1시간판. 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md A (2026-10-18 01:10).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from btc_intraday_study import CONF, FULL, TRAIN, Data, simulate, v1  # noqa: E402
from btc_v2_preverdict import BASE, VARIANTS, agg, windows  # noqa: E402


def short_count(r: dict, hourly: bool) -> int:
    lim = 3 * 3600 if hourly else 86400
    return sum(1 for a, b, *_ in r["trade_list"] if (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() <= lim)


def main() -> int:
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"   # 2026-10-18: ETHUSDT 같은 표
    D = Data(sym)
    print(f"[{sym}]")
    cfg = {"v1 일봉": (False, False), "v1 1시간": (True, False), "A-d 일봉+게이트": (False, True), "A-h 1시간+게이트": (True, True)}
    out = {}
    print("A. 진입 즉시 청산 금지 수정판 — 1시간 모형 · 판정 아님(과대 추정)")
    for name, (hourly, gate) in cfg.items():
        row = {}
        for pn, (s, e) in (("학습", TRAIN), ("확인", CONF), ("전체", FULL)):
            r = simulate(D, v1(hourly, gate=gate), s, e, 0.0005)
            row[pn] = {"ret": r["ret"], "mdd": r["mdd"], "ratio": r["ratio"], "trades": r["trades"], "win": r["win"], "short": short_count(r, hourly)}
        p = dict(BASE, gate=gate)
        w = {"base": windows(D, hourly, p, 0.0005), "slip0.2%": windows(D, hourly, p, 0.002)}
        for k, v in VARIANTS:
            w[f"{k}={v}"] = windows(D, hourly, dict(p, **{k: v}), 0.0005)
        n7, ev = agg(w["base"])
        n6 = agg(w["base"], range(2020, 2026))[0]
        c3 = agg(w["slip0.2%"])[1] > 0
        c4 = all(agg(w[k])[1] > 0 for k in w if "=" in k)
        worst = min((agg(w[k])[1], k) for k in w if "=" in k)
        loss = sum(1 for x in w["base"] if x["ret"] < 0)
        row["win7"] = {"n7": n7, "n6": n6, "ev": ev, "c3": c3, "c4": c4, "worst": worst, "loss": loss}
        out[name] = row
        T, C, F = row["학습"], row["확인"], row["전체"]
        print(f"  {name:16s} 비율 학습 {T['ratio']:.2f} 확인 {C['ratio']:.2f} 전체 {F['ratio']:.2f} · 전체 {F['ret']:+.0%}·MDD {F['mdd']:.1%}·거래 {F['trades']}(짧은 보유 {F['short']})·승률 {F['win']:.0%}"
              f" | 7창 {n7}(6창 {n6})·거래당 {ev:+.0f}·C-3 {'O' if c3 else 'X'}·C-4 {'O' if c4 else 'X'}(최저 {worst[1]} {worst[0]:+.0f})·손실 창 {loss}/7")
    b = out["v1 일봉"]
    ad, ah = out["A-d 일봉+게이트"], out["A-h 1시간+게이트"]
    ok_d = ad["학습"]["ratio"] >= b["학습"]["ratio"] and ad["확인"]["ratio"] >= b["확인"]["ratio"]
    ok_h = ah["학습"]["ratio"] >= b["학습"]["ratio"] and ah["확인"]["ratio"] >= b["확인"]["ratio"] and ah["win7"]["c3"] and ah["win7"]["c4"]
    print(f"\n사전 기준: A-d {'v1 수정 후보(v2-d)' if ok_d else '폐기'} · A-h {'1시간판 후보(v2-h)' if ok_h else '폐기'}")
    f = LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-fix-gate{'' if sym == 'BTCUSDT' else '-' + sym}.json"
    f.write_text(json.dumps({"rows": out, "A-d": ok_d, "A-h": ok_h}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

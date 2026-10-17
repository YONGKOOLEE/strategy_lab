"""BB. crypto-trend v2 — 운영 L4·K2 영향 근사(1시간 저가). 사전 등록: research/2026-10-18-overnight-design.md BB (08:06)."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "research"))
from crypto_trend_replay import base_params, replay  # noqa: E402

PER = {"학습": (date(2017, 9, 1), date(2021, 12, 31)), "후기": (date(2022, 1, 1), date(2025, 12, 31)), "전체": (date(2017, 9, 1), date(2025, 12, 31))}


def ratio(r: dict, s: date, e: date) -> tuple[float, float, float]:
    ret, m = float(r["final"]) / 10000 - 1, float(r["mdd"])
    return ((1 + ret) ** (365.25 / ((e - s).days + 1)) - 1) / m, ret, m


out = {}
for l4 in (None, 0.05, 0.03, 0.02, 0.01):
    row = {}
    for pn, (s, e) in PER.items():
        r = replay(["BTCUSDT", "ETHUSDT"], base_params(2), s, e, skip_hours=frozenset({0}), l4=l4)
        rt, ret, m = ratio(r, s, e)
        row[pn] = {"ratio": rt, "ret": ret, "mdd": m, "trades": len(r["pnls"]), "k2_days": r["k2_days"], "blocked": r["blocked"]}
    out[str(l4)] = row
    f = row["전체"]
    print(f"L4 {'없음' if l4 is None else f'{l4:.0%}'}: 전체 {f['ret']:+.0%}·MDD {f['mdd']:.1%}·비율 {f['ratio']:.2f}·거래 {f['trades']}·K2 {f['k2_days']}일·막힌 매수 {f['blocked']} | 학습 {row['학습']['ratio']:.2f} · 후기 {row['후기']['ratio']:.2f}")
base, one = out["None"]["전체"]["ratio"], out["0.01"]["전체"]["ratio"]
drop = 1 - one / base
print(f"사전 기준: L4 1% 비율 변화 {-drop:+.0%} → {'운영 L4 1%와 충돌 — L4 재결정 또는 전략 조정 필요(사용자 결정)' if drop > 0.30 else 'L4 1%와 공존 가능'}")
(LAB / "results" / "cryptosim" / f"{date.today():%Y%m%d}-l4-k2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

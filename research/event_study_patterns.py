"""사건 연구 — 30종목 일봉(2016~2025)에서 컵앤핸들·VCP 근사 규칙(tools/patterns.py)의 사건 수와 돌파 뒤 수익 분포.
전략·백테스트가 아니다(한도·비용·슬롯 없음). 진입 = 돌파 확인 다음 날 시가, 수익 = 그 뒤 20·60거래일 종가 / 진입 시가 − 1 (비용 전).
같은 종목에서 사건 뒤 60거래일은 새 사건을 세지 않는다. 파라미터는 patterns.py 기본값(사전 고정).

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\event_study_patterns.py
출력: research/<날짜>-event-study-patterns.md
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import patterns as pt  # noqa: E402

COST_ROUNDTRIP = 0.0043   # 수수료 0.015%×2 + 매도세 0.20% + 슬리피지 0.1%×2 (참고선)


def load(path: Path) -> tuple[list[date], list[float], list[float], list[float]]:
    days, opens, closes, vols = [], [], [], []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            days.append(date.fromisoformat(r["date"]))
            opens.append(float(r["open"]))
            closes.append(float(r["close"]))
            vols.append(float(r["volume"]))
    return days, opens, closes, vols


def study(kind: str, detect) -> dict:
    events = []
    per_year: Counter = Counter()
    for f in sorted((LAB / "data" / "daily").glob("[0-9]*.csv")):   # 종목 코드만(KOSPI.csv 제외)
        days, opens, closes, vols = load(f)
        last_event = -10_000
        start = 272 if kind == "vcp" else 130
        for t in range(start, len(closes) - 61):
            if t - last_event < 60:
                continue
            ev = detect(closes[: t + 1], vols[: t + 1])
            if ev is None:
                continue
            entry = opens[t + 1]
            r20 = closes[t + 21] / entry - 1
            r60 = closes[t + 61] / entry - 1
            stop = ev.handle_low if kind == "cup" else ev.stop
            stop_dist = entry / stop - 1
            events.append((f.stem, days[t], entry, r20, r60, stop_dist))
            per_year[days[t].year] += 1
            last_event = t
    return {"events": events, "per_year": per_year}


def fmt_dist(vals: list[float]) -> str:
    if not vals:
        return "—"
    q = statistics.quantiles(vals, n=4) if len(vals) >= 4 else [min(vals), statistics.median(vals), max(vals)]
    win = sum(1 for v in vals if v > COST_ROUNDTRIP) / len(vals)
    return (f"n={len(vals)} 평균 {statistics.mean(vals)*100:+.2f}% 중앙 {statistics.median(vals)*100:+.2f}% "
            f"Q1 {q[0]*100:+.2f}% Q3 {q[-1]*100:+.2f}% 비용(0.43%) 초과 비율 {win:.0%}")


def main() -> int:
    n_stocks = len(list((LAB / "data" / "daily").glob("[0-9]*.csv")))
    out = [f"# 사건 연구 — 컵앤핸들·VCP 근사 규칙 ({date.today()}) — {n_stocks}종목", "",
           f"전략·백테스트가 아니다. {n_stocks}종목 2016~2025 일봉(생존편향 포함 — **모든 수익은 과대 추정**), 진입 = 돌파 확인 다음 날 시가, "
           "수익은 비용 전 종가 기준, 같은 종목 60거래일 내 중복 사건 제외. 파라미터 = tools/patterns.py 기본값(사전 고정, 조정 없음).", ""]
    for kind, detect, name in (("cup", pt.detect_cup_handle, "컵앤핸들(규칙 A)"), ("vcp", pt.detect_vcp, "VCP(규칙 B)")):
        res = study(kind, detect)
        ev = res["events"]
        out += [f"## {name}", f"- 사건 수: **{len(ev)}** ({n_stocks}종목 × 약 10년) → 연평균 {len(ev)/10:.1f}건, 연도별 {dict(sorted(res['per_year'].items()))}",
                f"- 20거래일 수익: {fmt_dist([e[3] for e in ev])}",
                f"- 60거래일 수익: {fmt_dist([e[4] for e in ev])}",
                f"- 진입가 대비 손절 거리: {fmt_dist([e[5] for e in ev]) if ev else '—'}", ""]
        if ev:
            by_stock = Counter(e[0] for e in ev)
            out.append(f"- 종목 분포(상위 5): {by_stock.most_common(5)}")
            out.append("")
            out.append("| 종목 | 돌파 확인일 | 진입 시가 | +20일 | +60일 | 손절 거리 |")
            out.append("|---|---|---|---|---|---|")
            for s, d, entry, r20, r60, sd in ev[:60]:
                out.append(f"| {s} | {d} | {entry:,.0f} | {r20*100:+.1f}% | {r60*100:+.1f}% | {sd*100:.1f}% |")
            if len(ev) > 60:
                out.append(f"| … | 외 {len(ev)-60}건 | | | | |")
            out.append("")
    out += ["## 해석 기준(사전)", "- 전략화 조건(ideas 카드): 사건 ≥ 창당(연) 10건 AND 60거래일 중앙 수익 > 비용 0.43%. 둘 중 하나라도 미달이면 전략화 보류.",
            "- 생존편향: 지금 시총 상위 30 = 과거에 베이스 돌파에 성공한 종목 → 패턴 전략에 가장 유리한 표본. 결과는 상한선으로만 읽는다.", ""]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-event-study-patterns-{n_stocks}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out[:40]))
    print(f"... 저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

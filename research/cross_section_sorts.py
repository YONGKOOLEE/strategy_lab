"""횡단면 정렬 연구 — ideas/2026-10-11-long-term-reversal.md 사전 등록 규칙 그대로. 전략 아님.
(a) 12-1개월 모멘텀 (b) 36개월 수익률로 21거래일마다 5분위 정렬, 이후 60/120/250거래일 수익(비용 전, 진입 t+1 시가).

실행: C:\\AI\\trading_system\\trading_system\\.venv\\Scripts\\python.exe C:\\AI\\strategy-lab\\research\\cross_section_sorts.py
출력: research/<날짜>-cross-section-sorts-<종목수>.md
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
STEP = 21
HORIZONS = (60, 120, 250)
SORTS = {"M1 12-1개월 모멘텀": (252, 21), "R1 36개월 수익률": (756, 0)}   # (lookback, skip)


def load_all():
    data = {}
    for f in sorted((LAB / "data" / "daily").glob("[0-9]*.csv")):
        d, o, c = [], [], []
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                d.append(r["date"]); o.append(float(r["open"])); c.append(float(r["close"]))
        data[f.stem] = (d, o, c)
    return data


def main() -> int:
    data = load_all()
    # 공통 거래일 축: 가장 긴 종목의 날짜 목록
    days = max((v[0] for v in data.values()), key=len)
    pos = {code: {dd: i for i, dd in enumerate(v[0])} for code, v in data.items()}
    out = [f"# 횡단면 정렬 연구 ({date.today()}) — {len(data)}종목", "",
           "사전 등록: ideas/2026-10-11-long-term-reversal.md. 전략 아님. 21거래일마다 5분위 정렬, 진입 t+1 시가, 비용 전. "
           "**생존편향 포함(현재 코스피200) — 특히 장기 패자의 반등이 과대 추정될 수 있음.** Q1 = 최저, Q5 = 최고.", ""]
    for name, (lb, skip) in SORTS.items():
        res = {h: defaultdict(list) for h in HORIZONS}          # h → quintile → returns
        base = {h: [] for h in HORIZONS}
        by_year = defaultdict(lambda: {"Q1": [], "Q5": [], "all": []})   # +250일 기준
        n_dates = 0
        for ti in range(lb + 5, len(days) - 251, STEP):
            day = days[ti]
            scores = []
            for code, (d, o, c) in data.items():
                i = pos[code].get(day)
                if i is None or i - lb < 0 or i + 251 >= len(c):
                    continue
                s = c[i - skip] / c[i - lb] - 1
                entry = o[i + 1]
                fwd = {h: c[i + 1 + h] / entry - 1 for h in HORIZONS}
                scores.append((s, fwd))
            if len(scores) < 50:
                continue
            n_dates += 1
            scores.sort(key=lambda t: t[0])
            q = len(scores) // 5
            for k in range(5):
                chunk = scores[k * q:(k + 1) * q] if k < 4 else scores[4 * q:]
                for _, fwd in chunk:
                    for h in HORIZONS:
                        res[h][f"Q{k+1}"].append(fwd[h])
            for _, fwd in scores:
                for h in HORIZONS:
                    base[h].append(fwd[h])
                by_year[day[:4]]["all"].append(fwd[250])
            for _, fwd in scores[:q]:
                by_year[day[:4]]["Q1"].append(fwd[250])
            for _, fwd in scores[-q:]:
                by_year[day[:4]]["Q5"].append(fwd[250])
        out += [f"## {name} — 정렬일 {n_dates}회", "", "| 구간 | 분위 | n | 평균 | 중앙 | 중앙 − 기준선 |", "|---|---|---|---|---|---|"]
        for h in HORIZONS:
            b = statistics.median(base[h])
            out.append(f"| +{h}일 | 기준선(전체) | {len(base[h])} | {statistics.mean(base[h])*100:+.2f}% | {b*100:+.2f}% | — |")
            for k in range(1, 6):
                v = res[h][f"Q{k}"]
                out.append(f"| +{h}일 | Q{k} | {len(v)} | {statistics.mean(v)*100:+.2f}% | {statistics.median(v)*100:+.2f}% | {(statistics.median(v)-b)*100:+.2f}pp |")
            spread = statistics.median(res[h]["Q5"]) - statistics.median(res[h]["Q1"])
            out.append(f"| +{h}일 | **Q5 − Q1 스프레드(중앙)** | | | {spread*100:+.2f}pp | |")
        out += ["", "연도별(+250일 중앙, 정렬일 연도): 연도 | Q1 | Q5 | 전체 | Q1−전체 | Q5−Q1"]
        for y in sorted(by_year):
            r = by_year[y]
            if not r["Q1"]:
                continue
            q1, q5, al = statistics.median(r["Q1"]), statistics.median(r["Q5"]), statistics.median(r["all"])
            out.append(f"- {y} | {q1*100:+.1f}% | {q5*100:+.1f}% | {al*100:+.1f}% | {(q1-al)*100:+.1f}pp | {(q5-q1)*100:+.1f}pp")
        out.append("")
    out += ["## 판정 기준(사전, 카드 참조)", "- R1: Q1(36개월 최저)의 +250일 중앙 − 기준선 ≥ +3pp AND 연도별 양수 ≥ 4/6 AND Q1 > Q5 → 우위 후보.",
            "- M1: Q5−Q1(+60일) 스프레드가 연도별로 부호가 뒤집히면 '약함'.", "- 생존편향: 장기 패자 중 편출·상장폐지 종목이 표본에 없다 → Q1 반등은 상한선."]
    path = LAB / "research" / f"{date.today():%Y-%m-%d}-cross-section-sorts-{len(data)}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

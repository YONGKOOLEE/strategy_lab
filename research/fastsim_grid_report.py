"""fastsim 그리드 결과 요약 — 축별 평균 효과·상위 조합·이웃 견고성(판정 아님, 다중 비교 주의).

실행: python research/fastsim_grid_report.py results/fastsim/<날짜>-grid1-p3.json [...여러 파일]
- 축별 효과: 그 축의 값마다 나머지 모든 조합의 중앙값(손익·MDD·손익/MDD·양수 연도).
- 상위 조합: 손익/MDD(=손익(만) ÷ MDD(%)) 순. 각 조합의 '이웃'(한 축만 한 칸 바꾼 조합들) 손익/MDD 중앙값을 함께 — 이웃도 좋으면 평탄한 영역.
"""

from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

AXES = ("stop", "entry", "align", "max_pos", "min_turnover", "rank_by", "vol_mult", "stop_pct")


def score(r: dict) -> float:
    return r["pnl"] / 1e4 / max(1e-9, r["mdd"] * 100)


def main(paths: list[str]) -> int:
    rows = []
    for p in paths:
        rows += json.loads(Path(p).read_text(encoding="utf-8"))
    for r in rows:
        r["score"] = score(r)
        r["pos_years"] = sum(1 for v in r["by_year"].values() if v > 0)
    axes = [a for a in AXES if len({r["params"][a] for r in rows}) > 1]
    print(f"조합 {len(rows)}개 · 축 {axes} — 판정 아님, 생존편향·다중 비교로 상위값은 과대")
    print("\n[축별 효과 — 값마다 나머지 조합의 중앙값]")
    for a in axes:
        g = defaultdict(list)
        for r in rows:
            g[r["params"][a]].append(r)
        print(f"  {a}:")
        for v, rs in sorted(g.items(), key=lambda kv: str(kv[0])):
            print(f"    {str(v):<10} 손익 {st.median(x['pnl'] for x in rs)/1e4:>8,.0f}만  MDD {st.median(x['mdd'] for x in rs):>6.1%}  "
                  f"손익/MDD {st.median(x['score'] for x in rs):>6.0f}  양수연도 {st.median(x['pos_years'] for x in rs):.0f}  거래 {st.median(x['trades'] for x in rs):.0f}")
    vals = {a: sorted({r["params"][a] for r in rows}, key=lambda x: (isinstance(x, str), x)) for a in axes}
    index = {tuple(r["params"][a] for a in axes): r for r in rows}

    def neighbors(r: dict) -> list[dict]:
        key = [r["params"][a] for a in axes]
        out = []
        for i, a in enumerate(axes):
            vs = vals[a]
            j = vs.index(key[i])
            for jj in (j - 1, j + 1):
                if 0 <= jj < len(vs):
                    k2 = list(key)
                    k2[i] = vs[jj]
                    if tuple(k2) in index:
                        out.append(index[tuple(k2)])
        return out

    print("\n[상위 15 조합 — 손익/MDD 순, 이웃 중앙값 함께]")
    for r in sorted(rows, key=lambda x: -x["score"])[:15]:
        nb = neighbors(r)
        nbs = st.median(x["score"] for x in nb) if nb else float("nan")
        lab = " ".join(f"{a}={r['params'][a]}" for a in axes)
        print(f"  {lab}\n     손익 {r['pnl']/1e4:,.0f}만 MDD {r['mdd']:.1%} 손익/MDD {r['score']:.0f} 양수 {r['pos_years']}/9 거래 {r['trades']} 승률 {r['win_rate']:.0%} "
              f"| 이웃 {len(nb)}개 손익/MDD 중앙 {nbs:.0f}")
    print("\n[양수 연도 8/9 이상 & MDD 30% 이하인 조합 수]", sum(1 for r in rows if r["pos_years"] >= 8 and r["mdd"] <= 0.30))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

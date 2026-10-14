"""R 단위 분포 — r3-trend류(고정 손절 1R) 결과 폴더의 trades.csv를 읽어 거래별 R = (청산가/진입가 − 1) / stop_pct 로 환산.
부분 감액은 운영 결과 파일에서 평균 청산가로 합쳐져 있으므로 R은 "거래 전체의 평균 R"이다.

실행: python research\\r_distribution.py <results/quick/<폴더>> [stop_pct=0.08]
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from pathlib import Path


def main(argv: list[str]) -> int:
    root = Path(argv[0])
    stop = float(argv[1]) if len(argv) > 1 else 0.08
    rows = []
    for f in sorted(root.glob("w*/trades.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            if r["손익"].strip():
                r["창"] = f.parent.name
                rows.append(r)
    if not rows:
        print("왕복 없음"); return 0
    rs = [((float(r["청산가"]) / float(r["진입가"]) - 1) / stop) for r in rows]
    b = Counter()
    for x in rs:
        if x <= -1.0: b["≤ −1R(손절·갭)"] += 1
        elif x < -0.5: b["−1R~−0.5R"] += 1
        elif x <= 0.5: b["본전(−0.5R~+0.5R)"] += 1
        elif x < 2.0: b["+0.5R~+2R"] += 1
        elif x < 3.0: b["+2R~+3R"] += 1
        else: b["≥ +3R"] += 1
    wins = sum(1 for x in rs if x > 0)
    print(f"폴더 {root.name}: 왕복 {len(rs)}, 실현 승률 {wins/len(rs):.0%}, 평균 {statistics.mean(rs):+.2f}R, 중앙 {statistics.median(rs):+.2f}R, "
          f"최악 {min(rs):+.2f}R, 최고 {max(rs):+.2f}R")
    for k in ["≤ −1R(손절·갭)", "−1R~−0.5R", "본전(−0.5R~+0.5R)", "+0.5R~+2R", "+2R~+3R", "≥ +3R"]:
        print(f"  {k}: {b.get(k, 0)} ({b.get(k, 0)/len(rs):.0%})")
    reasons = Counter(r["청산사유"] for r in rows)
    print(f"  청산사유: {dict(reasons)}")
    small = sum(1 for r in rows if int(float(r["수량"])) < 3)
    print(f"  분할 불가(수량 < 3주) 거래: {small} ({small/len(rows):.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

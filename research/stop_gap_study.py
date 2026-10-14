"""손절 갭 연구 — research/2026-10-12-stop-gap-study-design.md. 기술 분석(전략 아님)."""
from __future__ import annotations
import csv, statistics, sys
from collections import defaultdict
from datetime import date
from pathlib import Path
LAB = Path(__file__).resolve().parents[1]
STEP, MAX_HOLD = 21, 120

def load(f):
    d,o,h,l,c=[],[],[],[],[]
    for r in csv.DictReader(open(f,encoding="utf-8")):
        d.append(r["date"]); o.append(float(r["open"])); h.append(float(r["high"])); l.append(float(r["low"])); c.append(float(r["close"]))
    return d,o,h,l,c

def regime():
    p=LAB/"data/index/001.csv"
    ds,cs=[],[]
    for r in csv.DictReader(open(p,encoding="utf-8")): ds.append(r["date"]); cs.append(float(r["close"]))
    return {d:(None if i+1<200 else cs[i]>statistics.mean(cs[i-199:i+1])) for i,d in enumerate(ds)}

def main():
    reg=regime(); out=[f"# 손절 갭 연구 ({date.today()}) — 200종목", "", "설계: research/2026-10-12-stop-gap-study-design.md. 종가 −X% 판정 → 다음 날 시가 체결. 생존편향은 갭 통계에 영향 작음.", ""]
    for X in (0.08, 0.12):
        real, gap, intraday, byy, byr = [], [], [], defaultdict(list), {"up":[], "down":[]}
        n_dec=0
        for f in sorted((LAB/"data/daily").glob("[0-9]*.csv")):
            d,o,h,l,c=load(f)
            for i in range(260, len(c)-MAX_HOLD-3, STEP):
                n_dec+=1; e=o[i+1]; thr=e*(1-X)
                for t in range(i+1, i+1+MAX_HOLD):
                    if c[t] < thr:
                        r=o[t+1]/e-1; real.append(r); gap.append(r-(-X)); byy[d[t][:4]].append(r)
                        st=reg.get(d[t]); 
                        if st is not None: byr["up" if st else "down"].append(r)
                        # 장중 손절 이상치: 저가가 thr 아래 찍은 첫날 thr 체결(갭 하락 시가면 시가)
                        k=next((k for k in range(i+1, t+1) if l[k] < thr), t)
                        intraday.append((min(o[k], thr))/e-1)
                        break
        s=sorted(real); n10=max(1,len(s)//10)
        out += [f"## X = {X:.0%} (1R)", f"- 결정 {n_dec}건 중 손절 사건 **{len(real)}**({len(real)/n_dec:.0%})",
                f"- 종가 판정·다음 날 시가 실손실: 평균 {statistics.mean(real)*100:+.2f}% (= {statistics.mean(real)/X:+.2f}R), 중앙 {statistics.median(real)*100:+.2f}% ({statistics.median(real)/X:+.2f}R), 최악 10% 평균 {statistics.mean(s[:n10])*100:+.2f}% ({statistics.mean(s[:n10])/X:+.2f}R)",
                f"- 갭 비용(실손실 − (−X)): 평균 {statistics.mean(gap)*100:+.2f}pp, 중앙 {statistics.median(gap)*100:+.2f}pp; 분포: 0~−1pp {sum(1 for g in gap if g>-0.01)/len(gap):.0%}, −1~−3pp {sum(1 for g in gap if -0.03<g<=-0.01)/len(gap):.0%}, −3pp 이하 {sum(1 for g in gap if g<=-0.03)/len(gap):.0%}",
                f"- 장중 손절 이상치(저가 첫 이탈일 −X 체결, 갭이면 시가): 평균 {statistics.mean(intraday)*100:+.2f}% ({statistics.mean(intraday)/X:+.2f}R) → 장중 손절의 가치 상한 ≈ {(statistics.mean(intraday)-statistics.mean(real))*100:+.2f}pp/손절",
                f"- 국면별 실손실 평균: 상승 {statistics.mean(byr['up'])*100:+.2f}% / 하락 {statistics.mean(byr['down'])*100:+.2f}%",
                "- 연도별 실손실 평균(R): " + ", ".join(f"{y} {statistics.mean(v)/X:+.2f}R" for y,v in sorted(byy.items())), ""]
    p=LAB/"research"/f"{date.today():%Y-%m-%d}-stop-gap-200.md"; p.write_text("\n".join(out),encoding="utf-8"); print("\n".join(out)); print("저장:",p)
if __name__=="__main__": sys.exit(main())

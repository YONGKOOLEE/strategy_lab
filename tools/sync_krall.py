"""운영 전 종목 일봉(kiwoom-krall-adj-*) → 전략실 data/krall 사본. 운영 저장소는 읽기만 한다.

- 종류 필터(기본 보통주만): 우선주·스팩·리츠 제외. ETF·ETN은 원본에 일봉 없음.
- **관리종목 표시(managed)로 거르지 않는다** — 지금 시점 상태라 과거 백테스트에 쓰면 룩어헤드.
- cutoff(기본 2026-01-01) 이후 행은 잘라낸다(D-163 최종 확인 구간). 잘라낸 뒤 행이 없으면(2026 상장) 복사하지 않는다.
- 열은 운영 로더 형식 그대로(date,open,high,low,close,volume,amount — 로더는 amount를 무시).
- 30% 초과 변동 표시(2026-10-17): 운영 품질 검사는 전일 대비 |변동| > 30%이고 corporate_action 표시가 없으면 이상치로 보고
  그날부터 그 종목을 판정에서 뺀다. 수정주가 반올림으로 상·하한가가 30.0x%가 된 행(30~32%)과 거래정지(5일 안 거래량 0) 뒤 재개 행은
  실제 거래이므로 corporate_action=1을 붙인다(운영 로더가 지원하는 열). 그 밖(정지 없이 32% 초과)은 수정 오류 가능성 → 표시 안 함(이상치 유지).
- 지수: index/001.csv → data/krall/KOSPI.csv(기존 data/daily와 같은 이름, 국면 규칙용), index/101.csv → data/krall-index/101.csv.
- data/krall/SOURCE.txt에 출처·필터·종목 수 기록. 상장폐지 종목 없음(원본 README) → 생존편향.
실행: python tools/sync_krall.py [--source <폴더>] [--kinds 보통주] [--cutoff 2026-01-01]
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SRC_DEFAULT = Path(r"C:\AI\trading_system\trading_system\var\backtest\data\kiwoom-krall-adj-20261017")


def copy_trunc(src: Path, dst: Path, cutoff: str, flag: Counter | None = None) -> int:
    lines = src.read_text(encoding="utf-8").splitlines()
    keep = [lines[0]] + [ln for ln in lines[1:] if ln[:10] < cutoff]
    if len(keep) <= 1:
        return 0
    if flag is not None:   # 30% 초과 변동 표시(모듈 설명 참고)
        hdr = keep[0].split(",")
        ci, vi = hdr.index("close"), hdr.index("volume")
        rows = [ln.split(",") for ln in keep[1:]]
        out = [keep[0] + ",corporate_action"]
        for k, r in enumerate(rows):
            mark = "0"
            if k:
                pc, cc = Decimal(rows[k - 1][ci]), Decimal(r[ci])
                if pc > 0 and abs(cc - pc) / pc > Decimal("0.30"):
                    if any(Decimal(rows[j][vi]) == 0 for j in range(max(0, k - 5), k)):
                        mark = "1"
                        flag["정지 뒤 재개"] += 1
                    elif abs(cc - pc) / pc <= Decimal("0.32"):
                        mark = "1"
                        flag["상하한가 반올림"] += 1
                    else:
                        flag["이상치 유지(>32%·정지 없음)"] += 1
            out.append(",".join(r) + "," + mark)
        keep = out
    dst.write_text("\n".join(keep) + "\n", encoding="utf-8")
    return len(keep) - 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(SRC_DEFAULT))
    ap.add_argument("--kinds", default="보통주", help="쉼표 구분(보통주,우선주,스팩,리츠)")
    ap.add_argument("--cutoff", default="2026-01-01")
    ap.add_argument("--overwrite", action="store_true", help="기존 data/krall 파일을 덮어쓴다(삭제는 하지 않음)")
    ns = ap.parse_args(argv)
    src = Path(ns.source)
    kinds = {k.strip() for k in ns.kinds.split(",") if k.strip()}
    out, out_idx = LAB / "data" / "krall", LAB / "data" / "krall-index"
    if out.exists() and any(out.iterdir()) and not ns.overwrite:
        print(f"이미 있음(지우고 다시): {out}")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    out_idx.mkdir(parents=True, exist_ok=True)
    with (src / "meta" / "stocks.csv").open(encoding="utf-8") as f:
        meta = [r for r in csv.DictReader(f) if r["market"] in ("KOSPI", "KOSDAQ")]
    picked = [r for r in meta if r["kind"] in kinds]
    stats: Counter = Counter()
    flags: Counter = Counter()
    names = []
    for r in picked:
        p = src / f"{r['code']}.csv"
        if not p.exists():
            stats["원본 없음"] += 1
            continue
        n = copy_trunc(p, out / p.name, ns.cutoff, flags)
        if n == 0:
            stats["cutoff 이후 상장(제외)"] += 1
            continue
        stats[r["market"]] += 1
        names.append((r["code"], r["name"], r["market"], r["kind"], r["managed"]))
    copy_trunc(src / "index" / "001.csv", out / "KOSPI.csv", ns.cutoff)
    copy_trunc(src / "index" / "101.csv", out_idx / "101.csv", ns.cutoff)
    with (out_idx / "names.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "market", "kind", "managed_now"])
        w.writerows(names)
    (out / "SOURCE.txt").write_text(
        f"source={src}\nkinds={','.join(sorted(kinds))}\ncutoff={ns.cutoff}\nsynced={datetime.now():%Y-%m-%d %H:%M}\n"
        f"stocks={sum(stats[m] for m in ('KOSPI', 'KOSDAQ'))} (KOSPI {stats['KOSPI']}, KOSDAQ {stats['KOSDAQ']})\n"
        f"excluded={dict((k, v) for k, v in stats.items() if k not in ('KOSPI', 'KOSDAQ'))}\n"
        f"corporate_action={dict(flags)}\n"
        "index=KOSPI.csv(001); KOSDAQ 101 → data/krall-index/101.csv\n"
        "note=상장폐지 종목 없음(생존편향). managed 표시로 거르지 않음(현재 상태 = 룩어헤드). 종목명은 data/krall-index/names.csv\n",
        encoding="utf-8")
    print((out / "SOURCE.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

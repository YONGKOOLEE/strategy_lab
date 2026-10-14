"""모드 2(사용자 목록) 시험용 일봉 폴더 만들기 — data/daily에서 지정 종목 CSV + KOSPI.csv(국면 입력)를 data/lists/<이름>/ 로 복사.
운영 백테스트는 폴더 전체를 유니버스로 보므로, 이 폴더가 곧 "사용자가 준 목록"이다.

실행: python tools\\make_list.py <이름> 000080 000100 ...   (코드는 6자리, 공백 구분)
     python tools\\make_list.py <이름> --file <코드 목록 txt(한 줄에 하나)>
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    name = argv[0]
    if argv[1] == "--file":
        codes = [x.strip() for x in Path(argv[2]).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    else:
        codes = argv[1:]
    src = LAB / "data" / "daily"
    dst = LAB / "data" / "lists" / name
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob("*.csv"):
        old.unlink()
    missing = []
    for c in codes:
        f = src / f"{c}.csv"
        if f.exists():
            shutil.copy(f, dst / f.name)
        else:
            missing.append(c)
    if (src / "KOSPI.csv").exists():
        shutil.copy(src / "KOSPI.csv", dst / "KOSPI.csv")
    (dst / "LIST.txt").write_text("\n".join(codes) + "\n", encoding="utf-8")
    print(f"목록 '{name}': {len(codes) - len(missing)}종목 복사 + KOSPI → {dst}" + (f" / 없음: {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

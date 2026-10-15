"""탐색 스윕 — 파라미터 그리드의 모든 조합을 quick 탐색 모드(--explore-start)로 돌리고 한 표로 모은다(판정 아님).

- 기준 파라미터 파일의 해당 줄만 바꾼 조합별 파일을 results/sweep/<날짜>-<후보>-<이름>/params/ 에 만든다(따옴표 형식 유지).
- 조합마다 운영 .venv 파이썬으로 tools/quick.py를 따로 실행(BelowNormal 우선순위, --jobs개 동시). 로그는 logs/<조합>.log.
- 시간 규칙(CLAUDE.md §2, 2026-10-14 사용자 결정으로 시간 금지 해제): 언제든 실행, 항상 BelowNormal. 평일 06:40~16:00에 시작하면 --jobs 최대 8.
  --deadline HH:MM을 주면 그 전에 못 끝날 조합(지금까지 최장 소요 기준)은 시작하지 않는다 — 남은 조합은 "미실행"으로 남고 --resume으로 이어서 돈다.
- 결과: summary.md(조합별 거래·승률·거래당 기대값·근사 R·연도별·최악 연도), summary.json. 모든 수치는 생존편향 포함(과대 추정)·탐색(검증 구간 포함).

실행 예(운영 .venv 파이썬):
  python tools/sweep.py --candidate r3_trend --cls R3TrendV7 --version 7 --name stage1 \
      --grid "adv_min=0.3,0.5,0.7;depth_max=0.25,0.35;vol_mult=1.5,2.0" --limits research/limits-explore-r3v7.toml --jobs 6
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Lock

LAB = Path(__file__).resolve().parents[1]
OPS_DEFAULT = Path(r"C:\AI\trading_system\trading_system")
BELOW_NORMAL = 0x00004000


def _daytime(now: datetime) -> bool:
    return now.weekday() < 5 and now.replace(hour=6, minute=40, second=0) <= now < now.replace(hour=16, minute=0, second=0)


def _deadline(now: datetime, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    d = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return d if d > now else d + timedelta(days=1)


def _parse_grid(text: str) -> list[tuple[str, list[str]]]:
    out = []
    for part in text.split(";"):
        if not part.strip():
            continue
        k, vs = part.split("=", 1)
        out.append((k.strip(), [v.strip() for v in vs.split(",") if v.strip()]))
    return out


def _write_params(base_text: str, combo: dict[str, str], path: Path) -> None:
    text = base_text
    for k, v in combo.items():
        pat = re.compile(rf'^(\s*{re.escape(k)}\s*=\s*)("?)[^"#\n]*("?)', re.M)
        if not pat.search(text):
            raise SystemExit(f"기준 파라미터 파일에 {k} 줄이 없음")
        text = pat.sub(lambda m: f"{m.group(1)}{m.group(2)}{v}{m.group(3)}", text, count=1)
    path.write_text(text, encoding="utf-8")


def _label(name: str, combo: dict[str, str]) -> str:
    return name + "-" + "-".join(f"{k}{v}" for k, v in combo.items()).replace("_", "")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="sweep.py")
    p.add_argument("--candidate", required=True)
    p.add_argument("--cls", required=True)
    p.add_argument("--version", type=int, required=True)
    p.add_argument("--name", required=True, help="스윕 이름(결과 폴더·라벨 접두)")
    p.add_argument("--grid", required=True, help='"키=값1,값2;키2=값1,값2"')
    p.add_argument("--base-params", default=None, help="기준 파라미터 파일(기본 candidates/<후보>/params-v<n>.toml)")
    p.add_argument("--explore-start", default="2017-01-01")
    p.add_argument("--explore-end", default="2025-12-31")
    p.add_argument("--limits", default=None)
    p.add_argument("--data", default=None)
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--deadline", default=None, help="HH:MM — 이 시각 전에 못 끝날 조합은 시작하지 않음(기본 없음)")
    p.add_argument("--resume", action="store_true",
                   help="이미 결과가 있는 조합은 건너뛴다. 같은 후보·이름의 가장 최근 스윕 폴더를 이어 쓴다(날짜가 바뀌어도)")
    p.add_argument("--ops", default=str(OPS_DEFAULT))
    ns = p.parse_args(argv)

    folder = LAB / "candidates" / ns.candidate
    base = Path(ns.base_params) if ns.base_params else folder / f"params-v{ns.version}.toml"
    grid = _parse_grid(ns.grid)
    combos = [dict(zip([k for k, _ in grid], vals)) for vals in itertools.product(*[vs for _, vs in grid])]
    root = LAB / "results" / "sweep" / f"{date.today():%Y%m%d}-{ns.candidate}-{ns.name}"
    if ns.resume:  # 2026-10-15: 날짜가 바뀐 뒤 --resume이 새 폴더에서 전부 다시 돌던 결함 수정
        prev = sorted((LAB / "results" / "sweep").glob(f"*-{ns.candidate}-{ns.name}"))
        if not prev:
            print(f"--resume: 이어 쓸 스윕 폴더 없음(*-{ns.candidate}-{ns.name})")
            return 2
        root = prev[-1]
        print(f"--resume: {root.name} 이어 씀")
    elif root.exists():
        print(f"이미 있음(--resume 또는 다른 --name): {root}")
        return 2
    (root / "params").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    base_text = base.read_text(encoding="utf-8")
    py = Path(ns.ops) / ".venv" / "Scripts" / "python.exe"
    state_path = root / "state.json"
    state: dict[str, dict] = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    lock = Lock()
    longest = [max((s.get("seconds", 0) for s in state.values()), default=0.0)]
    deadline = _deadline(datetime.now(), ns.deadline) if ns.deadline else None
    if _daytime(datetime.now()) and ns.jobs > 8:
        print(f"평일 장중(06:40~16:00): jobs {ns.jobs} -> 8 (PAPER 보호)")
        ns.jobs = 8
    dl = f"마감 {deadline:%m-%d %H:%M}" if deadline else "마감 없음"
    print(f"스윕 {ns.name}: 조합 {len(combos)}개, 동시 {ns.jobs}, 구간 {ns.explore_start}~{ns.explore_end}, {dl}")

    def run(combo: dict[str, str]) -> None:
        lab = _label(ns.name, combo)
        with lock:
            if ns.resume and state.get(lab, {}).get("status") == "ok":
                return
            now = datetime.now()
            if deadline is not None and now + timedelta(seconds=longest[0]) > deadline:
                state[lab] = {"combo": combo, "status": "미실행(시간)"}
                return
        pf = root / "params" / f"{lab}.toml"
        _write_params(base_text, combo, pf)
        cmd = [str(py), str(LAB / "tools" / "quick.py"), "--candidate", ns.candidate, "--cls", ns.cls,
               "--version", str(ns.version), "--params", str(pf), "--label", lab,
               "--explore-start", ns.explore_start, "--explore-end", ns.explore_end, "--ops", ns.ops]
        if ns.limits:
            cmd += ["--limits", str(Path(ns.limits).resolve())]
        if ns.data:
            cmd += ["--data", ns.data]
        t0 = _time.monotonic()
        with (root / "logs" / f"{lab}.log").open("w", encoding="utf-8") as log:
            rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(LAB),
                                creationflags=BELOW_NORMAL if sys.platform == "win32" else 0).returncode
        secs = round(_time.monotonic() - t0, 1)
        text = (root / "logs" / f"{lab}.log").read_text(encoding="utf-8", errors="replace")
        m = re.search(r"결과 폴더: (.+)", text)
        rec: dict = {"combo": combo, "status": "ok" if rc == 0 else f"실패 rc={rc}", "seconds": secs}
        if rc == 0 and m:
            sp = Path(m.group(1).strip()) / "quick-summary.json"
            if sp.exists():
                rec["summary"] = json.loads(sp.read_text(encoding="utf-8"))
        with lock:
            state[lab] = rec
            longest[0] = max(longest[0], secs)
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            print(f"[{datetime.now():%H:%M}] {lab}: {rec['status']} {secs}초", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, ns.jobs)) as ex:
        list(ex.map(run, combos))
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    _report(root, state, [k for k, _ in grid], ns)
    return 0


def _report(root: Path, state: dict[str, dict], keys: list[str], ns: argparse.Namespace) -> None:
    lines = [f"# 스윕 {ns.name} — {ns.candidate} v{ns.version} (탐색, 판정 아님)", "",
             f"구간 {ns.explore_start}~{ns.explore_end} 연속 1회 · 한도 {ns.limits or '운영 기본'} · "
             "**생존편향 포함(과대 추정)·검증 구간 포함·여러 조합 중 고른 값은 사후 선택** — 확인은 2026 최종 구간·PAPER.", "",
             "근사 R = 거래당 기대값 ÷ (초기 자금 1억 × risk_ratio). 피라미딩·익절 감액이 있으면 근사.", "",
             "| " + " | ".join(keys) + " | 상태 | 거래 | 승률% | 거래당 기대값(원) | 근사 R | 손익 합계(원) | 양수 연도 | 최악 연도 | 평균 보유 | 첫 진입 |",
             "|" + "---|" * (len(keys) + 10)]
    for lab, rec in sorted(state.items()):
        c = rec.get("combo", {})
        s = rec.get("summary")
        cells = [c.get(k, "") for k in keys] + [rec.get("status", "")]
        if s:
            rr = Decimal(str(s["params"].get("risk_ratio", "0.01")))
            exp = s["expectancy"]
            approx_r = f"{Decimal(exp) / (Decimal('100000000') * rr):.2f}" if exp not in ("—", None) and rr > 0 else "—"
            ys = s.get("years", [])
            pos = sum(1 for y in ys if Decimal(y["pnl"]) > 0)
            worst = min(ys, key=lambda y: Decimal(y["pnl"])) if ys else None
            cells += [str(s["trades"]), s["win_rate"], exp, approx_r, s["pnl"], f"{pos}/{len(ys)}",
                      f"{worst['year']} {worst['pnl']}" if worst else "—", s["avg_hold"], str(s.get("first_entry"))]
        else:
            cells += ["—"] * 9
        lines.append("| " + " | ".join(cells) + " |")
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "summary.json").write_text(json.dumps(state, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n결과: {root / 'summary.md'}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

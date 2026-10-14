"""후보 구조 검사 — 운영 저장소로 옮기기 전에 운영 `tests/architecture` 규칙을 전략실에서 미리 적용한다.

검사 항목:
 1. import 규칙: 표준 라이브러리 + trading_system.domain·trading_system.strategy만, 금지 stdlib(os·pathlib·time·random·
    socket…)·현재 시각 호출 없음 — 운영 `tests/architecture/import_rules.check_source`를 그대로 사용(읽기만).
 2. 전략실 추가 규칙: 운영 `strategy.candidates`의 비공개 도우미(`_xxx`) import 금지(옮긴 뒤 깨짐), `tools.indicators` import 금지(인라인 복사).
 3. 전략 적재: `패키지.모듈:클래스`로 인스턴스를 만들고 spec·evaluate가 있는지, params-v<n>.toml이 spec 허용 범위를 통과하는지
    (운영 `load_strategy`와 같은 경로).
 4. 3파일 존재: strategy.md·strategy.py·params-v<n>.toml, strategy.md의 빈 칸 수(운영 양식은 모든 칸 필수).

실행(운영 .venv 파이썬, 운영 저장소에 쓰기 없음):
  tools\\check-candidate.ps1 -Candidate <폴더> -Class <클래스> -Version <n>
종료 코드 0 = 통과, 1 = 위반 있음, 2 = 실행 불가.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
OPS_DEFAULT = Path(r"C:\AI\trading_system\trading_system")
PRIVATE_IMPORT = re.compile(r"^from\s+trading_system\.strategy\.candidates\s+import\s+.*\b_[a-z]", re.M)


def _imports(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="check-candidate.py")
    p.add_argument("--candidate", required=True, help="candidates 아래 폴더 이름")
    p.add_argument("--cls", required=True, help="strategy.py 안의 클래스 이름")
    p.add_argument("--version", type=int, required=True)
    p.add_argument("--ops", default=str(OPS_DEFAULT))
    ns = p.parse_args(argv)

    ops = Path(ns.ops)
    folder = LAB / "candidates" / ns.candidate
    py = folder / "strategy.py"
    md = folder / "strategy.md"
    toml = folder / f"params-v{ns.version}.toml"
    problems: list[str] = []
    for f in (py, md, toml):
        if not f.exists():
            problems.append(f"파일 없음: {f}")
    if problems:
        print("\n".join(problems))
        return 2

    sys.path.insert(0, str(ops / "src"))
    sys.path.insert(0, str(ops))          # tests.architecture
    sys.path.insert(0, str(LAB))          # candidates.<name>.strategy
    from tests.architecture.import_rules import check_source  # type: ignore[import-not-found]

    source = py.read_text(encoding="utf-8")
    # 1. 운영 규칙을 "운영 strategy 패키지 안의 모듈"로 가정하고 적용
    for v in check_source(source, f"trading_system.strategy.{ns.candidate}"):
        problems.append(f"[운영 구조 규칙] {py.name}:{v.line}: {v.reason}")
    # 2. 전략실 추가 규칙
    tree = ast.parse(source)
    for name in _imports(tree):
        if name.startswith("tools") or name == "indicators":
            problems.append(f"[전략실 규칙] `{name}` import 금지 — tools/indicators.py의 함수는 strategy.py에 인라인 복사한다")
        if name.startswith("candidates."):
            problems.append(f"[전략실 규칙] `{name}` import 금지 — 후보끼리 의존하지 않는다(옮기면 깨짐)")
    if PRIVATE_IMPORT.search(source):
        problems.append("[전략실 규칙] 운영 strategy.candidates의 비공개 도우미(_xxx) import 금지 — 그 모듈은 '제안·미등록'이라 바뀔 수 있다")
    # 3. 적재·파라미터 검증 (운영과 같은 경로). 배분 규칙(kind=ALLOCATION)은 decide()만 있으므로 직접 적재
    try:
        import importlib
        from trading_system.config.strategy_params import load_params_file
        obj = getattr(importlib.import_module(f"candidates.{ns.candidate}.strategy"), ns.cls)()
        if getattr(obj.spec, "kind", "STRATEGY") == "ALLOCATION":
            if not hasattr(obj, "decide"):
                problems.append("[배분 규칙] decide(index, params) 없음")
            if not obj.spec.allocation_targets:
                problems.append("[배분 규칙] allocation_targets 비어 있음")
            strat, params = obj, load_params_file(obj.spec, toml.resolve())
        else:
            from trading_system.app.wiring import load_strategy
            from trading_system.config.app_file import StrategyDeploy
            strat, params = load_strategy(StrategyDeploy(f"candidates.{ns.candidate}.strategy:{ns.cls}", toml.resolve(), ()))
        spec = strat.spec
        print(f"적재 OK: {spec.strategy_id} v{spec.version}, 규칙 {len(spec.rules)}개, 파라미터 {sorted(params)}")
        if spec.version != ns.version:
            problems.append(f"[버전] spec.version={spec.version} ≠ params 파일 버전 {ns.version} (규칙·파라미터 변경 시 둘 다 올린다)")
        # 규칙 입력 표기: 운영 등록 검사는 선언한 CAP-ID 정확 일치 또는 "상태 입력"만 허용(괄호 설명 등 붙이면 등록 거부)
        allowed_inputs = set(spec.capabilities) | {"상태 입력"}
        for r in spec.rules:
            bad = [x for x in r.inputs if x not in allowed_inputs]
            if bad:
                problems.append(f"[규칙 입력] {r.rule_id}: {bad} — 선언한 CAP-ID({sorted(spec.capabilities)}) 또는 '상태 입력'만 쓴다(설명은 condition에)")
            if r.kind not in {"ENTRY", "INCREASE", "REDUCE", "EXIT", "REENTRY_BLOCK", "ALLOCATION"}:
                problems.append(f"[규칙 종류] {r.rule_id}: '{r.kind}'는 운영 규칙 종류가 아니다")
        ids = {"paper0-verify", "trend-sma", "example-sma"}
        if spec.strategy_id in ids or spec.strategy_id.startswith("cand-"):
            problems.append(f"[ID] 전략 ID '{spec.strategy_id}'는 운영 기존 ID와 겹치거나 견본 ID — 다른 ID를 쓴다")
    except Exception as exc:  # noqa: BLE001 — 어떤 오류든 적재 실패로 보고
        problems.append(f"[적재 실패] {type(exc).__name__}: {exc}")
    # 4. strategy.md 빈 칸
    md_text = md.read_text(encoding="utf-8")
    empty_fields = re.findall(r"^- [^:\n]+:\s*$", md_text, re.M)
    if empty_fields:
        problems.append(f"[strategy.md] 값이 비어 있는 항목 {len(empty_fields)}개: " + "; ".join(x.strip() for x in empty_fields[:5]))
    if "생존편향" not in md_text and "과대 추정" not in md_text:
        problems.append("[strategy.md] 생존편향·과대 추정 한계 문장 없음(전략실 규칙)")

    if problems:
        print("위반 " + str(len(problems)) + "건:")
        print("\n".join(" - " + x for x in problems))
        return 1
    print("구조 검사 통과 — 운영 저장소로 옮길 때 변환 없이 구조 시험을 통과할 가능성이 높다(최종 판정은 운영 세션).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

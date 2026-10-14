---
name: new-candidate
description: 견본 candidates/example_sma를 복사해 새 후보 폴더를 만들고 ID·클래스·버전·strategy.md·notes.md 사전 등록 절을 채운다(R1~R2 준비). 사용 예 - /new-candidate donchian_breakout
---

# /new-candidate — 새 후보 폴더 만들기

입력: `$ARGUMENTS` = `<폴더_이름_밑줄> [ideas 카드 경로]`. 폴더 이름이 없으면 1개 질문으로 묻는다.

## 절차
1. `candidates/<이름>/`이 이미 있으면 중단하고 알린다. 전략 ID(`<이름>`을 하이픈으로 바꾼 것, 예 `donchian-breakout`)가 운영 기존 ID(`paper0-verify`, `trend-sma`, `cand-*`)·`example-sma`와 겹치지 않는지 확인한다.
2. `candidates/example_sma/`의 `strategy.py`·`strategy.md`·`params-v1.toml`을 읽어 새 폴더에 **새 파일로** 쓴다(복사 뒤 치환):
   - `strategy.py`: 모듈 docstring(견본 문구 제거, 규칙을 말로), `STRATEGY_ID`, 클래스 이름(`<PascalCase>V1`), `build_spec`의 name·description·rules·params·data_requirements·holding, `evaluate` 본문. **import는 표준 라이브러리 + `trading_system.domain.*` + `trading_system.strategy.base`만**. 지표가 더 필요하면 `tools/indicators.py`에서 함수를 **복사해 인라인**한다(import 금지). 아이디어 카드가 주어졌으면 그 규칙을 코드로 옮기되, 모호한 조건은 코드로 쓰지 말고 질문 목록에 올린다(최대 5개, 차단/비차단 구분).
   - `params-v1.toml`: `strategy = "<ID>"`, `version = 1`, `[params]`에 ParamSpec과 같은 이름·허용 범위 안의 초기값. 소수는 문자열.
   - `strategy.md`: 운영 양식의 모든 칸을 채운다(비면 운영 등록 거부). 실패 국면 표·한계 절(생존편향·과대 추정 문장 필수) 포함. 모르는 칸은 "미확인(확인 주체: 사용자)"으로 적되 비워 두지 않는다.
3. `notes.md`를 만들고 맨 위에 **사전 등록** 절을 쓴다(R2):
   ```markdown
   # <ID> 기록
   ## 사전 등록 (v1, <날짜>) — 실행 뒤 변경 금지
   - 가설: <카드의 "왜 수익이 나야 하는가" 요약>
   - 파라미터 초기값·근거: …
   - 폐기 기준: 1차 선별(창 4·7 합산) 거래당 기대값 ≤ 0 또는 거래 < 10 → 폐기 / validate "미충족" → 폐기 또는 v+1(사유 기록)
   - 시도 상한: v1 5회(trials.jsonl 기준)
   ## 기록
   ```
4. 구조 검사를 **실행**한다(가벼움, 시간 제한 없음):
   `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\check-candidate.ps1 -Candidate <이름> -Class <클래스> -Version 1`
   위반이 있으면 고치고 다시 실행한다. 통과 출력을 notes.md 기록 절에 한 줄로 적는다.
5. 보고: 만든 파일 목록, 구조 검사 결과(실제 출력 요약), 미결 질문, 다음 행동 — `critic` 에이전트 검토 뒤 사용자가 붙여 넣을 quick 명령:
   `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\quick.ps1 -Candidate <이름> -Class <클래스> -Version 1`
   (평일 06:40~16:00 거부. 기대 결과: 창별 표와 "1차 판단: …")

## 하지 않는 것
quick·validate를 사용자 지시 없이 실행하지 않는다(무거움·시간 제한). 운영 저장소에 쓰지 않는다. 폐기 기준을 결과를 보고 고치지 않는다.

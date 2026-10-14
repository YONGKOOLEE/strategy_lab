---
name: handoff
description: 전략실 후보를 운영 저장소(trading_system)로 넘길 인계 패킷 candidates/<후보>/handoff.md를 만든다 — 3파일·검사 기록·판정표·시도 횟수·한계·운영 세션에 붙일 지시문. 사용 예 - /handoff donchian_breakout
---

# /handoff — 운영 인계 패킷 (R5 → 운영 저장소)

입력: `$ARGUMENTS` = 후보 폴더 이름. 전략실은 패킷까지만 만든다. **운영 저장소에 쓰지 않는다.**

## 선행 확인 (하나라도 아니면 패킷을 만들지 않고 무엇이 빠졌는지 보고)
- `tools/check-candidate.ps1` 통과 기록이 notes.md에 있다(없으면 지금 실행 — 가벼움).
- 최신 버전의 validate 판정표(`results/…/validation-v<n>.md`)가 있고 판정이 "통과" 또는 "통과(과대 추정 가능)"다. "미충족"·"판단 불가"면 인계 불가 — 사용자가 그래도 넘기길 원하면 패킷에 "판정 미충족 상태 인계(사용자 결정)"를 굵게 적는다.
- notes.md 사전 등록 절이 있고, trials.jsonl 횟수가 시도 상한 안이다(넘었으면 그 사실을 적는다).

## handoff.md 내용
```markdown
# 인계 패킷 — <ID> v<n> (<날짜>)
전략실 결과는 연구 참고다. 공식 판정·등록·PAPER·LIVE는 운영 저장소 절차와 사용자 승인(A-ID)으로만.

## 파일 (전략실 경로 → 운영 목적지 제안)
| 파일 | 전략실 | 운영 |
|---|---|---|
| strategy.py | candidates/<후보>/strategy.py | src/trading_system/strategy/<모듈>.py |
| params-v<n>.toml | … | config/strategies/<ID>-v<n>.toml |
| strategy.md | … | docs/strategies/<ID>/strategy.md |

## 전략실 검증 기록
- 구조 검사: <날짜> 통과(출력 요약)
- quick 시도: <trials.jsonl 횟수>회, 라벨 목록
- validate 판정표: <경로> — 판정 … / C-2 … / C-3 … / C-4 … / 손실 창 … / 운영 커밋 … / 호가 표 …
- 사전 등록 폐기 기준과 결과 대조: …

## 한계 · 미확인 (운영에서 확인할 것)
- 생존편향: 유니버스 사후 선택 30종목 → 운영 공식 판정에서도 C-7 "과대 추정" 표시 예상
- 운영 설정 차이(호가 표·슬리피지·한도)가 바뀌면 수치가 달라짐
- 전략 고유 미확인: …

## 운영 세션에 붙일 지시문 (사용자가 복사)
전략실 후보 <후보> v<n>을 공식 판정해 줘. 파일은 C:\AI\strategy-lab\candidates\<후보>\ 의 strategy.py·params-v<n>.toml·strategy.md.
브랜치에서 복사 → 구조 시험 → scripts\validate-strategy.py 공식 판정표(유니버스 사후 선택이면 C-7 표시) → 결과 보고. 등록·PAPER 투입은 내가 따로 승인한다.

## 운영 측 이후 절차 (참고)
구조 시험 → 공식 판정표 → `strategy.py register` → BACKTEST_PASSED(A-ID) → 사용자 승인 → `app.paper.toml` 등록 → PAPER-1(최소 20거래일·전략별 거래 수·슬리피지 허용치) → 07-paper-review → LIVE 체크리스트(04 §5.1 C-01~C-14, 별도 승인). 전략실은 "실전 준비 완료"를 선언하지 않는다.
```

보고: 패킷 경로, 선행 확인 결과, 사용자가 복사할 지시문.

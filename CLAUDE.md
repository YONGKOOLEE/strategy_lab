# CLAUDE.md — 전략실 (strategy-lab)

전략 아이디어를 많이 만들어 보고 버리는 **연구 전용** 저장소다. 운영 저장소(`C:\AI\trading_system\trading_system`)와 분리한다(운영 승인 A-085).
한국어로 근거·절차·결과 중심으로 간결하게 답한다. 사용자는 터미널 명령에 익숙하지 않다 — 실행 안내는 복사해 붙일 전체 명령과 기대 결과로 준다.

## 0. 역할
너는 전략 연구원이다. 목표는 "통과하는 전략"을 만드는 것이 아니라 **빨리 버릴 수 있는 근거**를 만드는 것이다.
- 실행 전에 폐기 기준을 적고, 실행 뒤 기준을 바꾸지 않는다.
- 수익률보다 **거래당 기대값·슬리피지 2배 견고성·파라미터 ±20% 견고성·창별 일관성**을 본다(운영 CP-030 C-1~C-8). 지금 계좌 한도(보유 3종목·1회 100만 원)에서는 수익률이 전략 우위를 거의 말해 주지 않는다.
- 모든 수치에 "생존편향 포함, 과대 추정"을 붙인다(데이터가 현재 구성 종목뿐 — 2026-10-11부터 코스피200 200종목, 그 전 30종목).
- 파라미터 조정은 학습 창 안에서만, 시도 횟수를 기록한다(`trials.jsonl`). 결과를 좋게 보이게 만드는 선택(기간·종목·기준 바꾸기)을 하지 않는다.
- 지금 지원 능력(일봉·09:30 1회 판정·시장가·보유 3·일 5건·1회 100만 원) 밖의 아이디어는 `ideas/`에 "CP-032 뒤"로 분류하고 구현하지 않는다.
- 사용자 제공 사실, 실행으로 확인한 결과, 가정, 미확인을 구분한다. 실행하지 않은 것을 실행했다고 말하지 않는다.

## 1. 이 저장소에서 하는 일
- 아이디어 카드(`ideas/`), 자유 분석(`research/`), 후보 전략(`candidates/<전략>/`), 1차 선별(`tools/quick.ps1`), 미리 돌려 보기(`tools/validate.ps1`), 결과 기록(`results/`, `notes.md`).
- 여기서 나온 결과는 **연구 참고**다. 공식 판정(CP-030)·등록·PAPER·LIVE는 운영 저장소 절차로만 한다(§6).
- 운영 저장소의 단계·승인 규칙은 여기서 적용하지 않는다. 대신 §2 금지와 §5 절차는 항상 지킨다.

## 2. 항상 금지
- 증권사·거래소 연결(키움·바이낸스 등), 주문 관련 코드·명령, 네트워크로 시세 받기. 데이터는 `data/` 사본만 쓴다. 운영의 `fetch-daily.py`·`kiwoom-probe.py` 등 네트워크 스크립트를 실행하지 않는다.
- 비밀정보: 앱키·시크릿·토큰·계좌번호를 요청·저장·출력하지 않는다. 운영 저장소의 `.env*` 파일을 읽지 않는다.
- **운영 저장소에 쓰기 금지.** 운영 저장소는 (a) 읽기 (b) 운영 `.venv` 파이썬으로 운영 코드를 import·실행하는 것(검증 실행기, `tools/quick.py`, `tools/check-candidate.py`)만 한다. 결과는 항상 이 저장소 `results/`로. 운영 `config/`·`docs/`·`src/`·`var/`를 고치지 않는다. 후보를 운영으로 옮기는 일은 사용자가 운영 세션에서 지시할 때 그쪽에서 한다(§6).
- 자동 실행 등록(작업 스케줄러 등), push, 패키지 설치(필요하면 목적·영향을 설명하고 승인받는다). 운영 `.venv`에는 표준 라이브러리 + pytest·requests·websockets만 있다 — pandas 없음.
- 평일 06:40~16:00에 무거운 실행(quick·validate) 금지 — 같은 PC에서 PAPER 무인 운영이 돈다. 스크립트가 거부한다(평일 휴장일은 `-Holiday`).

## 3. 데이터 규칙
- `data/`는 git 제외. 원본(2026-10-11부터)은 운영 `var\backtest\data\kiwoom-kospi200-adj-20261009`(키움 일봉, 수정주가, **코스피200 현재 구성 200종목** + `index/001.csv` KOSPI 지수 → `data/index/`). 어떤 원본을 썼는지는 `data/SOURCE.txt`. 다시 받으려면 `tools\sync-data.ps1`(이전 30종목은 `-Source …\kiwoom-ka10081-adj-20261007`). 2026-10-11 이전 결과(results/)는 30종목 기준 — 200종목 결과와 섞어 비교하지 않는다.
- **운영 CP-034(2026-10-12, A-092~094) 이후**: 한도는 운영 승인 연구 프로필 `C:\AI\trading_system\trading_system\config\limits.research.toml`(L1 0.5%+여유 3%·L7 = 기준 금액 10% 비율·L4 2%·전략별 L6 3)을 `validate.ps1 -Limits`로 쓴다(전략실 `research/limits-*.toml` 사본은 **대체됨**, 기록용). legacy 기본 프로필(상한가 L1) 결과와 **섞어 비교하지 않는다**. U-B 전략 명세는 `universe_method="U-B", universe=(), universe_list="<목록ID>"`, 스냅샷에 `listed_at`. 국면 필터는 **배분 규칙**(kind=ALLOCATION, `candidates/regime_kospi/`)으로 두고 `validate.ps1 -Allocation … -AllocationParams … -Index`로 대조 판정(운영 Q-9 기준). 판정 시점 목록은 `-UniverseHistory`(진짜 시점별 목록일 때만 — 정적 목록에 쓰면 C-7 표시가 사라지므로 금지).
- 200종목에서 실행 시간은 30종목의 약 7배(quick 창당 약 17분, validate 91회는 수 시간) → validate는 `-Workers 4` 이상·밤에만. 모든 사건 연구·전략 결과는 **기준선(모든 날 진입 분포)** 과 함께 보고한다(`research/event_study_price_volume.py`).
- **2026-01-01 이후는 최종 확인 구간**(운영 D-163). 연구·파라미터 선택에 쓰지 않는다. `data/daily/`에는 2025-12-31까지만(sync가 잘라 냄). 최종 확인은 전략 확정 뒤 운영 저장소에서 버전당 1회.
- 워크포워드 창(운영 D-162): k=1..7, 학습 3년·검증 1년, 검증 2019~2025. 파라미터는 학습 창 안에서 사람이 고른다.
- 한계 문장(항상 함께 적음): 생존편향(사후 선택 30종목), 수정주가 반올림, 호가 표·VI·거래정지 이력 미반영, 장중 손절 없음, 비용 가정(수수료 0.015%·매도세 0.20%·슬리피지 0.1%).

## 4. 후보 전략 규격 (운영으로 변환 없이 옮길 수 있게)
- 폴더 `candidates/<이름_밑줄>/`: `strategy.md`(운영 양식 `docs/templates/strategy-template.md`, 모든 칸 채움), `strategy.py`, `params-v<n>.toml`, `notes.md`, `trials.jsonl`(도구가 자동 기록).
- `strategy.py`는 **자기완결**: 표준 라이브러리 + `trading_system.domain`·`trading_system.strategy.base`만 import. 지표·크기 도우미는 `tools/indicators.py`에서 **복사해 인라인**한다(import 금지). 운영 `strategy.candidates`의 비공개 도우미(`_xxx`)·다른 후보·`tools` import 금지. 파일·네트워크·현재 시각·난수 금지. `tools/check-candidate.ps1`이 운영 구조 규칙으로 검사한다.
- 규칙은 입력·판정 시점·조건·행동·무효 조건이 결정 가능해야 한다. 전일까지 확정 일봉만 본다(룩어헤드 0). 종목마다 신호 최대 1개, 청산 > 진입. 손절가는 신호에 실어 크기 계산(S-3)에 쓴다.
- 전략 ID는 운영 기존 ID(`paper0-verify`, `trend-sma`, `cand-*`)·견본 ID(`example-sma`)와 겹치지 않게. 규칙·파라미터를 바꾸면 `VERSION`·`params-v<n>`·`strategy.md` 버전을 함께 올린다(이전 결과 승계 없음).
- 계좌 한도는 전략이 공유한다(보유 3·일 5건·1회 100만 원, 운영 A-034). 전략별 한도는 계좌 한도 이하.

## 5. 연구 절차 (R0 → R5, 기본값은 "폐기")
| 단계 | 산출물 | 통과 조건 |
|---|---|---|
| R0 아이디어 카드 (`/idea`) | `ideas/<날짜>-<이름>.md` | 왜 수익이 나야 하는지 한 문단, 실패 국면, 필요 능력(지금 가능 / CP-032 뒤) |
| R1 규칙화 (`spec-writer` → `critic`) | `candidates/<이름>/strategy.md` 규칙 표 | 모호한 조건 0, 룩어헤드 0, 능력 범위 안. critic 지적 "차단" 0 |
| R2 사전 등록 | `notes.md` 맨 위 "사전 등록" 절 | 파라미터 초기값·허용 범위·**폐기 기준**(예: 창 4·7 합산 거래당 기대값 ≤ 0 → 폐기)·시도 상한(버전당 5회)을 실행 **전에** 기록 |
| R3 1차 선별 (`tools/quick.ps1`) | `results/quick/…`, `trials.jsonl` | 폐기 기준 미달이면 여기서 폐기(기록 남김). 재시도는 라벨을 바꾸고 상한 안에서 |
| R4 미리 돌려 보기 (`tools/validate.ps1`, 저녁) | `results/<날짜>-<이름>/…/validation-v<n>.md` | C-1~C-8 판정표 그대로 읽음(`/read-results`). "미충족"이면 사유 기록 후 폐기 또는 v+1 |
| R5 결론 | `notes.md` 두 줄 + 한계 문장 | 폐기 / 보류(이유) / 운영 인계 요청(`/handoff`) |

과최적화 방지: 폐기 기준 사후 변경 금지 · 시도 상한 초과 시 폐기 또는 사용자 결정 · 창·종목·판정 시각을 결과 보고 고르지 않음 · 변형이 기본과 "결과 동일"이면 그 파라미터는 시험되지 않은 것으로 봄 · 결과 해석에 항상 §3 한계 문장.

## 6. 운영 인계 (trading_system에서 검증 → PAPER → LIVE)
- 전략실은 **인계 패킷**까지만 만든다(`/handoff <이름>` → `candidates/<이름>/handoff.md`): 3파일 경로·버전, check-candidate 통과 기록, validate 판정표 경로·판정·사유, trials 횟수, 한계·미확인, 운영 세션에 붙일 지시문.
- 운영 세션에서 사용자가 하는 절차(참고): 3파일 복사(브랜치) → 구조 시험 → `scripts\validate-strategy.py` 공식 판정표(유니버스는 판정 시점 목록이 아니면 C-7 표시) → `strategy.py register` → BACKTEST_PASSED(A-ID) → 사용자 승인 → `app.paper.toml` 등록 → PAPER-1(최소 20거래일·전략별 거래 수) → `07-paper-review` → LIVE 체크리스트(04 §5.1 C-01~C-14).
- 전략실 판정은 운영 판정을 대신하지 않는다. "실전 준비 완료"라고 말하지 않는다. LIVE 승인·실전 주문 코드는 운영 저장소의 별도 승인이다.

## 7. 도구 (PowerShell에 그대로 붙여 넣기 — README에 기대 결과)
| 도구 | 용도 | 무게 |
|---|---|---|
| `tools\sync-data.ps1` | 운영 일봉 → `data/daily`(2025-12-31까지) | 가벼움 |
| `tools\check-candidate.ps1 -Candidate <폴더> -Class <클래스> -Version <n>` | 운영 구조 규칙·적재·파라미터 범위·strategy.md 빈 칸 | 수 초 |
| `tools\quick.ps1 … [-Windows 4,7] [-Label base]` | 창 1~2개 1차 선별, `trials.jsonl` 기록 | 창당 약 2.5분(30종목) |
| `tools\quick.ps1 … -Train [-TrainStart 2017-01-01] -Label train-<값>` | 학습 창(2016~2018) 실행 — 파라미터 선택용, 판정 아님 | 창당 수 분~17분 |
| `tools\validate.ps1 …` | 운영 검증 실행기 전체(91회) | 약 86분 — 저녁에 백그라운드 |
| `python -m pytest tools\test_indicators.py tools\test_patterns.py` | 지표·패턴 검출기 시험 | 수 초 |
| `quick.ps1 … -Label scaleB -Params <scale params> -Limits research\limits-scale-test-l1fix.toml` | 규모 실험(판정 아님, "미결정 한도 가정" 표시) | 창당 약 2.5분 |
| `python research\event_study_patterns.py` | 패턴 사건 연구(전략 아님, 기술 분석) | 수 초~분 |

## 8. 기록과 세션
- 의미 있는 실행은 `results/`(git 제외)에 남고 결론은 `notes.md`에. 폐기한 아이디어도 이유와 함께 `ideas/` 카드에 "폐기" 표시로 남긴다(같은 아이디어를 다시 시도하지 않게).
- 세션 시작: **`research/HANDOFF.md`를 먼저 읽는다**(현재 상태·다음 할 일·규칙), 그 뒤 `git status`, 필요한 `candidates/*/notes.md`, `ideas/` 미처리 카드를 보고 "진행 중 후보·다음 행동"을 한 줄로 보고한다. 운영 저장소 HEAD(읽기)를 함께 적는다 — 운영 설정(호가 표 등)이 바뀌면 전략실 수치도 바뀐다.
- 세션 종료: 변경 파일, 실행한 명령과 실제 결과, 다음 행동을 보고한다. 커밋은 사용자가 지시할 때만.
- 스킬: `/idea`, `/new-candidate`, `/read-results`, `/compare`, `/handoff`. 에이전트: `critic`(비판 검토, 읽기 전용), `spec-writer`(카드 → 규칙 표), `result-reader`(결과 폴더 요약·비교).

## 9. 모델 사용 규칙 (사용자 지시 2026-10-13, 토큰 효율)
- **메인 세션**은 사용자가 고른 모델(기본 Opus 또는 Fable)로 돈다. 메인이 모델을 바꾸지 않는다.
- **프로젝트가 스스로 판단해**, 아래 "Sonnet 가능" 업무는 서브에이전트에 `model: "sonnet"`으로 위임하거나 정해진 sonnet 에이전트(result-reader·spec-writer)를 쓴다. 판단이 필요한 업무는 강한 모델이 직접 한다.
- 위임한 결과 중 **결론·판정에 쓰는 수치는 메인이 원본 파일 1~2곳을 직접 대조**한 뒤 쓴다(서브에이전트 보고를 그대로 옮기지 않는다).

| 구분 | 업무 |
|---|---|
| **Sonnet 가능(위임)** | 결과 파일 읽기·표 요약·R 분포/창별 통계 집계 · 정해진 명령 실행·진행률 확인·로그 기록 · 양식이 정해진 문서 칸 채우기·worklog/notes 일상 기록 · 파일 지도·색인 정리 · 단순 문헌·출처 정리 · 사전 등록된 연구 스크립트의 기계적 변형(파라미터 파일 생성, 결과 폴더 이동) · 구조 검사 실행·출력 보고 |
| **강한 모델 유지** | 사전 등록 설계(판정·폐기 기준·시도 상한) · 사후 선택 여부 판단 · 결과 해석·결론(채택/기각/보류)과 "틀릴 수 있는 지점" · 전략 코드 작성·수정(룩어헤드·운영 규격) · 운영 인터페이스(CP) 해석·운영 세션에 보낼 질의·제안 · critic 검토 · 실행 중단 같은 원인 분석 · CLAUDE.md·HANDOFF 구조 변경 · 사용자에게 하는 설명 |
- 토큰 절약: 큰 파일은 전체를 읽지 말고 grep/sed 범위로, 긴 로그·서브에이전트 transcript(output 파일)는 열지 않고 완료 보고만 쓴다, 같은 내용을 보고에서 반복하지 않는다, 반복되는 통계 집계는 스크립트로 한 번에.

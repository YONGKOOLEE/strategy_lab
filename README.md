# 전략실 (strategy-lab)

전략 아이디어를 연구하는 곳. 운영(자동매매) 저장소와 분리되어 있어 여기서 무엇을 해도 PAPER 운영에 영향을 주지 않는다. 규칙·절차는 [CLAUDE.md](CLAUDE.md).

## 폴더
| 폴더 | 용도 | git |
|---|---|---|
| `ideas/` | 아이디어 카드(`/idea`), 다른 AI와 만든 초안 | 포함 |
| `research/` | 자유 분석(스크립트·비교표) | 포함 |
| `candidates/<이름>/` | 후보 전략: `strategy.md`·`strategy.py`·`params-v<n>.toml`·`notes.md`·`trials.jsonl`(시도 장부, 자동)·`handoff.md`(인계 패킷) | 포함 |
| `data/` | 키움 일봉 사본(2025-12-31까지): `daily/` 코스피200 200종목(2026-10-11부터), `index/001.csv` KOSPI, 휴장일, `SOURCE.txt`(원본 기록) | 제외 |
| `results/` | `quick/`(1차 선별), `<날짜>-<후보>/`(검증 실행기 판정표) | 제외 |
| `tools/` | 아래 명령 스크립트, `indicators.py`(지표 원본)·`patterns.py`(패턴 검출기, 연구용) + 시험 | 포함 |
| `.claude/` | 권한(`settings.local.json`), 스킬(`skills/`), 에이전트(`agents/`) | 포함 |

## 연구 흐름 (Claude Code 대화에서)
1. `/idea <한 줄>` → 아이디어 카드 (R0)
2. `/new-candidate <이름> ideas/<카드>` → 후보 폴더 + 사전 등록(폐기 기준·시도 상한) + 구조 검사 (R1~R2). `critic` 에이전트로 검토.
3. 아래 **1차 선별** 명령을 붙여 넣어 실행 (R3). 기대값 ≤ 0이면 폐기.
4. 저녁에 **미리 돌려 보기** 명령 실행 (R4) → `/read-results results\<폴더>` 로 판정표 요약·결론 기록 (R5).
5. `/compare` 로 후보 비교. 판정 "통과"면 `/handoff <이름>` → 인계 패킷의 지시문을 **운영 세션**에 붙인다.

## 자주 쓰는 명령 (PowerShell에 그대로 붙여 넣기)
1. 데이터 다시 복사 — 기대 결과 `복사 30 종목, …`
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\sync-data.ps1
   ```
2. 후보 구조 검사(수 초) — 기대 결과 `적재 OK: …` 뒤 `구조 검사 통과` 또는 `위반 N건` 목록
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\check-candidate.ps1 -Candidate example_sma -Class ExampleSmaV1 -Version 1
   ```
   (견본은 "견본 ID" 위반 1건이 정상 — 새 후보는 다른 ID를 쓴다.)
3. 1차 선별(창 2개, 약 5분. 우선순위 BelowNormal로 언제든) — 기대 결과 창별 표, `합산 | 거래 N | 거래당 기대값 …원`, `1차 판단: …`
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\quick.ps1 -Candidate example_sma -Class ExampleSmaV1 -Version 1
   ```
   창을 바꾸려면 ` -Windows 1,2,3`, 파라미터를 바꿔 다시 돌리면 ` -Label <라벨>`(결과 폴더·시도 장부 구분). 평일 휴장일 낮에는 ` -Holiday`.
   학습 창(파라미터 선택용, 판정 아님): ` -Train -TrainStart 2017-01-01 -Label train-<값> -Params <파일>` — 창 1 학습 구간(2016~2018) 안에서만 실행, 연도별 표·첫 진입일 출력, 장부 tool=quick-train.
   규모 실험(판정 아님): ` -Label scaleB -Params <후보>\params-v<n>-scale-cap10m.toml -Limits C:\AI\strategy-lab\research\limits-scale-test-l1fix.toml` — 결과에 "사용자 미결정 한도 가정" 표시.
4. 미리 돌려 보기(검증 실행기 전체 91회, 약 86분. 언제든, 평일 장중 workers 최대 8) — 기대 결과 `판정: …` 과 `종료 코드 0, 결과 폴더 …`
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI\strategy-lab\tools\validate.ps1 -Candidate example_sma -Class ExampleSmaV1 -Version 1
   ```
   저녁에 돌려 두고 다음 날 `results\<날짜>-<폴더>\<전략ID>-v<n>\validation-v<n>.md` 판정표(C-1~C-8)부터 본다.
5. 지표 라이브러리 시험(수 초) — 기대 결과 `8 passed`
   ```
   & 'C:\AI\trading_system\trading_system\.venv\Scripts\python.exe' -m pytest 'C:\AI\strategy-lab\tools\test_indicators.py' -q -p no:cacheprovider
   ```

## 알아 둘 것
- 전략실 수치는 **운영 저장소의 현재 코드·설정**(호가 표, 슬리피지, 한도)에 따라 달라진다. quick·validate 출력의 "운영 코드 커밋"이 같은 결과끼리만 비교한다.
- 모든 결과는 생존편향 포함(사후 선택 30종목) → 과대 추정. 현재 한도(보유 3·1회 100만 원)에서는 수익률이 아니라 거래당 기대값을 본다.
- 운영 `.venv`에는 pandas가 없다. 지표는 `tools/indicators.py`(Decimal, 표준 라이브러리)를 쓰고, 후보 `strategy.py`에는 필요한 함수를 복사해 넣는다.

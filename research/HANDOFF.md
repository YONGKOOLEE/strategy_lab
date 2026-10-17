# 전략실 세션 인계 (HANDOFF) — 2026-10-18 02:24 기준 (date 확인)

**새 세션은 이 파일 하나만 먼저 읽는다.** 세부는 §8 파일 지도에서 필요한 것만 연다. 시각은 항상 `date`로 확인해 적는다(추정 금지). 실행 중인 작업: **없음**(01:50 전략실 python 0개 확인).

## 1. 한 줄 상태
**코인(M2 바이낸스 현물) 우선.** 밤샘 연구(2026-10-18 01:00~01:50, 사용자 지시 "오전 7시까지 계속 — ETH 오면 같은 시험·개선·튜닝 확인 → 인계")로 **새 후보 `candidates/crypto_trend` v1**(BTC·ETH 2종목, 60분 판정, 진입 게이트, 종목별 위험 2.5%)을 만들고 critic 차단 4건 반영·구조 검사 통과·운영 엔진 호환 확인까지 함 → **사용자 결정 대기**(운영 전달 시점·유니버스 A-096 변경·규모). 기존 `btc_trend` v1은 운영이 검토 중(재현 일치). 한국 주식은 개별 종목 기계식 매매 우위 없음(밤샘에 코인 구조도 폐기) — 방향 결정 대기, 새 선택지 (d) 코스피 지수 ETF 추세(카드).

## 2. 코인 — 결론 요약 (상세 `research/2026-10-18-overnight-design.md` A~Y, 시각순 사전 등록·결과)
| 항목 | 결과 (판정 아님 — BTC·ETH 사후 선택, 과대 추정) |
|---|---|
| btc-trend v1(일봉) | 운영 재현 일치(40건·+6,498.6%·MDD 43.38%), 운영 판정 초안 = 판단 불가(C-2 6창 30건). lab-notice F-1~F-3(CAP-INS-05·validate_rules·validate_deploy)을 전략실 원본에 반영 |
| ETH(운영 수집 A-116) | v1이 ETH에서도 재현(24경계 학습 2.33·후기 0.66 vs 보유 0.72·−0.07, 엔진 7창 C-3·C-4 충족). 다른 계열은 BTC와 같은 결론 |
| 1시간 판정 + 게이트(가격 > SMA50) | 헛매매 제거(BTC 97건 중 61건 → 5건). BTC·ETH 모두 일봉보다 나음, 주변 격자 14/18·16/18칸, 수수료 0.2%에도 우위, 2종목 묶음 경계 24 중 19·23 우위. 단 BTC 단독 학습 구간은 일봉과 비슷(O — "UTC00 기댐" 주의) |
| 2종목 한 계좌 | 독립 반반 ≈ 한 계좌 위험 2.5%·상한 49%(G2). 운영 엔진(일봉판) L1 2.75%면 거부 0(J) |
| **crypto-trend v1** | strategy.py 재생(운영 23회 일정) 105건·+6,964%·MDD 33.5%, 학습 3.28·후기 1.33(반반 보유 0.80·0.11·MDD 86%). 7창 87건(C-2 미달)·C-3·C-4 충족·손실 창 1/7. 재표본: 상위 3건 빼도 중앙 12배(BTC 단독 v1 2.7배) |
| 폐기 | 일봉+게이트, 청산 일봉 혼합, 15분 판정, 앙상블, 재선택 튜닝(고정이 나음), 듀얼 모멘텀, 공유 계좌 확대(효율 아님), 변동성 돌파, VP 80% 규칙(실제 46%), 코인 구조의 한국 전 종목 이전 |
| 규모표(S) | 종목별 위험 1~5% → 전체 +830~16,767%·MDD 21~40%(v1 2.5% = +6,964%·33.5%). 사용자 결정 |
| PAPER 기간(U) | 28일이면 진입 0건 56%·왕복 0건 73%, 90일 10%·20% → PAPER 90일 이상 제안 |
| 한계 공통 | "후기 2022~2025"도 선택에 쓰임 → 표본 밖은 2026 최종 확인뿐. L4 1%(운영 M2)·K2 영향 미측정. 이익 집중(종목별 상위 3건 67~78%) |

## 3. 한국 주식 (M1)
- 전 종목 기계식 신고가·조정 돌파·(밤샘) 코인 구조 모두 손실(fastsim·운영 엔진, 생존편향 있는데도). 사용자 매매 우위 = 종목 선택(차트로 재현 안 됨).
- **선택지(사용자 결정)**: (a) 업종·수급·실적 데이터로 종목 선택 보강 (b) 사용자가 종목 선택·시스템은 규칙만 (c) 보류 (d) **코스피 지수 ETF 추세 추종** — 코스피 지수에서 v1 격자 17/18칸이 보유보다 수익/위험 우위(낙폭 절반, 수익은 비슷 이하), 코스닥은 아님. 카드 `ideas/2026-10-18-kospi-index-trend.md`, ETF 데이터·M1 ETF 매매 가능 여부 필요.

## 3-1. 운영에 보낸 요청과 답 (2026-10-18 02:24)
- 사용자 지시("전부 권장대로 … 운영세션 작업요청까지", 작업 끝나면 운영도 인계 준비)로 SendMessage 전달: A crypto-trend v1 검토, B ETH 유니버스 제안, C 상장폐지 포함 USDT 전 심볼 일봉 수집, D PAPER-1 90일 제안, E ETF 질의 + 운영 인계 준비 요청.
- 운영 답: **A·C는 운영 대화에서 사용자 승인 뒤 진행**(운영 규칙 — 전략실 전달은 승인이 아님). B·D는 운영 인계 문서의 사용자 결정 항목. E: ETF 일봉 [미확인]·소량 실측 필요, M1 ETF 매매는 CP 필요. CAP-TRG-02는 T-052 구현·미병합(M2 "검증 중"), T-068 미착수 — crypto-trend 재현을 T-053(1분봉 백테스트, 미병합)으로 할 수 있는지 운영이 검토 뒤 알림.
- 전략실 Z(생존편향 점검) 기준은 데이터 요청 전 고정(research/2026-10-18-overnight-design.md Z), 도구 research/crypto_universe_study.py 준비·점검 끝 — 데이터 오면 tools/sync_crypto.py로 사본 만든 뒤 바로 실행.

## 4. 다음 할 일 (사용자 결정 → 전략실 행동)
| # | 할 일 | 누가 | 메모 |
|---|---|---|---|
| ① | crypto-trend v1 검토 — **운영에 요청 전달함(A, 2026-10-18 02:2x)**. 운영 대화에서 사용자 승인 필요 | 사용자(운영 대화) | 재현은 운영 T-053(1분봉 백테스트)/T-068 뒤 — 운영이 가능 여부 알림 |
| ② | ETH 유니버스 추가 — 제안서 `research/proposal-ops-eth-expansion-2026-10-18.md` 운영에 전달함(B). 결정은 사용자 | 사용자 | A-096 변경 |
| ③ | 규모 결정(종목별 위험 1~5%, 규모표 S) + 운영 한도(L1 ≥ 2.75% 잠정, L4) | 사용자·운영 | |
| ④ | 상장폐지 포함 코인 수집 — **운영에 요청 전달함(C)**, 운영 대화에서 사용자 승인 필요 → 데이터 오면 전략실 Z 실행(기준·도구 준비 끝) | 사용자(운영 대화) → 전략실 | 생존편향 점검 |
| ⑤ | 운영 T-068 결과 오면: crypto_trend notes.md 맨 위 폐기 기준으로 대조(거래 ±15%·수익 ±30% 밖이면 원인 분석) | 전략실 | |
| ⑥ | 한국 방향 (a)~(d) | 사용자 | (d)는 운영 답: ETF 일봉 소량 실측 필요, M1 ETF 매매는 CP 필요(지금은 백테스트만) |
| ⑦ | PAPER-1 90일 제안(D)·ETF 질의 답(E) 반영됨 — 한국 (d)는 ETF 일봉 소량 실측·M1 ETF CP 필요 | 사용자 | |

## 5. 반드시 지킬 규칙
- 사전 등록 **저장 → 별도 호출로 실행**. 시각은 `date`로. 결과를 보고 기준·파라미터를 바꾸지 않는다. 이전 버전 코드는 보존. **실행 중인 후보의 strategy.py를 덮어쓰지 않는다**.
- 그리드에 (보유 수, 비중)처럼 짝이 있는 축은 **쌍별로 따로 실행**(2026-10-17 grid1, 2026-10-18 X에서 같은 실수 2번 — 기록됨).
- **같은 PC에서 PAPER 엔진(python)이 돈다**: 무거운 실행은 우선순위 BelowNormal·평일 06:40~16:00 병렬 최대 8. 이름 전체 종료 금지 — PID만. 전 종목 엔진 실행은 동시 6개 이하.
- 운영 저장소는 **읽기·운영 .venv로 코드 실행만**. `.env*` 읽기 금지, 네트워크·주문·거래소 연결 금지(데이터는 운영 수집분 사본만). 운영 세션과는 SendMessage로 정보만 주고받음(운영에 작업 지시는 사용자가).
- 2026-01-01 이후는 최종 확인 구간 — 백테스트·탐색·선택에 쓰지 않는다.
- 가정 한도(tools/m2_quick·two_coin_engine)는 **사용자 미결정 가정** — 운영 승인 한도와 섞어 비교하지 않는다.
- 사용자 성향: 승률보다 수익, 다양한 튜닝 결과를 직접 보고 싶어 함, 효율 우선, 쉬는 시간 없이 진행 원함, 터미널에 익숙하지 않음(복붙 명령 + 기대 결과), 한국어.

## 6. 모델 사용 규칙 (사용자 지시 2026-10-13)
메인은 사용자가 고른 모델. Sonnet 가능 업무는 `model: "sonnet"` 서브에이전트, 판단 업무(사전 등록·결과 해석·전략 코드·critic·운영 인터페이스 해석·원인 분석·사용자 설명)는 메인. 상세 CLAUDE.md §9.

## 7. 환경·메모
- 운영 HEAD(2026-10-18 01:50 읽기): 1f68720 "docs: binance-spot §14 상장폐지 심볼 확인 실험 결과 (A-117)". 운영 btc-trend 검토 브랜치 `feat/btc-trend-v1-review`(66d2781). 운영 승인: CP-039·CP-040(A-115 — 60·15분 주기, 01:00~23:00 23회, 1분 손절 감시, 장중 L4 1분 저가), A-116 ETH 수집, A-117 상장폐지 확인 실험. CP-038(저빈도 C-2 대체) 초안 — A-091 Q-5와 충돌, 사용자 결정 대기.
- 전략실 git: main, 원격 origin(GitHub YONGKOOLEE/strategy_lab) — push는 사용자가.
- 코인 데이터: `data/crypto/{BTCUSDT,ETHUSDT}-{1d,1h,15m}.csv`(2025-12-31까지, `tools/sync_crypto.py`), BTC 가격대 거래량 `BTCUSDT-vpbins.jsonl`.

## 8. 파일 지도
| 목적 | 경로 |
|---|---|
| **새 후보 crypto-trend** | `candidates/crypto_trend/{strategy.py,strategy.md,params-v1.toml,params-v1-paper.toml,notes.md(맨 위 사전 등록),trials.jsonl,handoff.md}` |
| btc-trend 후보·인계 | `candidates/btc_trend/{strategy.py(F-1~F-3 반영),strategy.md,params-v1*.toml,notes.md,handoff.md}` |
| 밤샘 연구 전부(A~Y) | `research/2026-10-18-overnight-design.md` |
| 이전 설계·결과 | `research/2026-10-17-crypto-design.md`, `research/2026-10-18-btc-preverdict-design.md`, `research/2026-10-18-intraday-design.md`, `research/2026-10-18-vp-design.md` |
| 코인 시뮬레이터·재생 | `tools/cryptosim.py`(일봉 1종목), `research/btc_intraday_study.py`(1시간 모형 — Data(sym, tf, offset), v1(hourly, gate, istop, exit_daily)), `research/crypto_trend_replay.py`(strategy.py를 운영 도메인 객체로 1시간 재생), `research/crypto_shared_account.py`(2종목 일봉 한 계좌) |
| 운영 엔진 실행 | `tools/m2_quick.py`(1종목, --module·--lot-step), `research/two_coin_engine.py`(2종목, `crypto-trend` 인자로 후보 호환성) |
| 운영에 보낼 제안서 | `research/proposal-ops-eth-expansion-2026-10-18.md`, `research/proposal-ops-intraday-2026-10-18.md` |
| 한국 | `tools/fastsim.py`(brk_n·gate_sma 추가), `research/2026-10-14-r3v7-explore-design.md`, `research/2026-10-16-user-trades-analysis.md`, 카드 `ideas/2026-10-18-kospi-index-trend.md` |
| 폐기 카드(재시도 금지) | `ideas/2026-10-18-{volume-profile-acceptance,volatility-breakout,dual-momentum,krx-crypto-structure}.md` |
| 작업 로그(시각순) | `research/worklog.md` |
| 지식 | 메모리 `C:\Users\user\.claude\projects\c--AI-strategy-lab\memory\` |

# 추세추종 패턴 학습 노트 — 컵앤핸들(Cup with Handle)·VCP(Volatility Contraction Pattern)

작성 2026-10-11 (사용자 지시 "추세추종 매매 수집·분석, cup with handle·VCP 학습"). 출처는 웹 2차 자료(교육 사이트·지표 스크립트·Bulkowski 사이트)이며 원저(O'Neil *How to Make Money in Stocks*, Minervini *Trade Like a Stock Market Wizard*)는 직접 확인하지 않았다 → 수치는 "통상 인용값"으로 본다. **확인된 사실 / 2차 자료 / 가정 / 미확인**을 구분해 적는다.

## 1. 컵앤핸들 (O'Neil, CAN SLIM 계열)

### 1.1 형태와 통상 규칙 (2차 자료, 출처 간 수치 불일치 있음)
| 요소 | 통상 인용값 | 비고 |
|---|---|---|
| 선행 상승 | 베이스 전 ≥ 30% 상승 | 추세 지속 패턴(상승 중 쉬는 구간) |
| 컵 깊이 | 고점 대비 12~33% (약세장 40~50%까지) | V자 급락·급반등은 컵이 아님(둥근 바닥) |
| 컵 길이 | 7~65주, 보통 3~6개월 | 일봉 35~325거래일 |
| 핸들 위치 | 베이스 상반부 | 하반부로 내려가면 조정 미완 |
| 핸들 깊이 | 8~12%, 또는 오른쪽 상승폭의 1/3 이하, 또는 컵 깊이의 33% 이하 | 출처별로 정의가 다름 |
| 핸들 기간 | 1~4주(최소 5일) | 거래량 감소하며 완만히 하락 |
| 매수점(피벗) | 핸들 고점 + 소폭(O'Neil은 10센트) | |
| 돌파 거래량 | 평균 대비 +40~50% 이상 | 컵 형성 중 거래량 감소 → 돌파 시 급증 |
| 손절 | 핸들 저점 아래(통상 7~8% 룰) | |

### 1.2 증거의 질
- **Bulkowski(thepatternsite.com)**: 913개 "완벽한" 거래 기준 성과 순위 3/39, 손익분기 실패율 5%, 평균 상승 54%, 되돌림(throwback) 62%, 목표 도달 61% — 강세장만. 같은 페이지의 다른 시험(300패턴, 1990~2024-03)에서는 **돌파 뒤 2개월 안에 47%가 크게 하락**. 패턴 식별이 사람 손(사후)이라 선택 편향 큼. 비용·슬리피지·시점별 유니버스 미반영.
- 2차 사이트의 "성공률 65%/70~85%" 류는 출처 없음 → 무시.
- 학술: Lo·Mamaysky·Wang(2000, J. Finance)이 커널 회귀로 고전 패턴(헤드앤숄더·이중천정 등)의 정보성을 검정 — 컵앤핸들 포함 여부·결론은 **미확인**(원문 미접근). 알고리즘적 컵 검출로는 Siligardos "semi-cup"(TASC 2011) 정도가 문서화돼 있고 성과 통계는 없음.
- 알고리즘 검출 지표(TradingView 스크립트)는 "림 대칭 허용 %·핸들 되돌림 비율(림-핸들)/(림-바닥) 범위"로 규칙화한다 — 우리 규칙화의 참고 틀.

## 2. VCP (Minervini, SEPA)

### 2.1 형태와 통상 규칙
- **수축**: 왼→오로 조정 폭이 줄어드는 2~4회(가끔 5~6회) 수축. 예: 1차 20~35% → 2차 10~20% → 3차 5~15% → 4차 3~8%. 핵심은 수치가 아니라 "매번 직전보다 좁아짐" + 마지막 구간 **거래량 고갈**.
- **진입**: 마지막 수축 고점(피벗) 돌파, 거래량 평균 +50% 이상. 손절은 마지막 수축 저점 아래, 최대 7~8%.
- **Trend Template(8항)**: 가격 > 150·200일선 / 150일선 > 200일선 / 200일선 1개월(이상적 4~5개월) 상승 / 50일선 > 150·200일선 / 가격 > 50일선 / 52주 저점 대비 ≥ +25% / 52주 고점 대비 −25% 이내(이상적 −15%).
- 추가(2차): RS 등급 > 70(혹은 85~90), 분기 EPS 성장 ≥ 20~25%, Stage 2만.

### 2.2 증거의 질
- 검증된(동료 평가·사전 고정 규칙·비용 반영·판정 시점 유니버스) 백테스트를 **찾지 못했다**. 상용 스크리너의 "+177% vs +45%"(2023-02~), 블로그의 "상위 100종목 중 36개가 VCP, 평균 +69%"는 유니버스·비용 미공개 또는 **사후 선택(승자 중에서 패턴 찾기)** 이라 과대 추정.
- 결론: 두 패턴 모두 "널리 쓰이지만 공개된 엄격한 증거는 없다". 우리 전략실의 사전 등록·워크포워드 절차가 그대로 필요하다.

## 3. 우리 환경에 맞추기 (일봉·09:30 1회·시장가·30종목)

### 3.1 가능한 것 / 없는 것
| 필요 요소 | 상태 |
|---|---|
| 일봉 OHLCV(거래량 포함) | **있음** — 패턴 검출·거래량 고갈·돌파 거래량 계산 가능. 단 "돌파 당일 거래량"은 09:30 판정 시점에 **알 수 없음**(전일 봉까지) → 돌파 확인은 **전일 종가·전일 거래량** 기준으로 하루 늦게 판정 |
| 50/150/200일선·52주 고저 | 계산 가능(워밍업 200~250거래일 → 2016년 창은 일부 종목 불가) |
| RS 등급(시장 대비 상대강도) | 30종목 안 상대 순위로 **근사**만 가능. 전체 시장 대비 RS는 유니버스 확장 필요 |
| EPS 성장·펀더멘털 | **없음**(CAP-DAT-05 미지원) → 제외하고 가격·거래량 규칙만 |
| 장중 피벗 돌파 매수·7~8% 장중 손절 | **불가**(일봉 1회·시장가) → 전일 종가 돌파 확인 뒤 당일 시가 매수, 손절은 종가 판정 |
| 패턴 빈도 | 30종목에서 엄격한 컵/VCP는 **드물다** → 7창 합산 100건(C-2) 미달 가능성 매우 높음 |

### 3.2 규칙화 초안 (결정 가능하게 — 파라미터는 사전 고정, 데이터로 조정 안 함)
**A. 컵앤핸들(일봉 근사)**
- 베이스 탐색 창 L(예 120거래일) 안에서: 좌측 림 = 창 내 최고 종가 H(위치 i), 바닥 = i 이후 최저 종가 B, 우측 림 = B 이후 최고 종가 R.
- 조건: 컵 깊이 12% ≤ (H−B)/H ≤ 33%; 바닥이 창의 중앙 40~60% 구간(둥근 바닥 근사: 바닥 전후 k일 평균이 바닥 대비 ±3% 이내); R ≥ 0.95H.
- 핸들: R 이후 5~20거래일 동안 최저 종가가 R 대비 −3~−12%, 핸들 저점 > (H+B)/2(상반부), 핸들 기간 평균 거래량 < 컵 기간 평균 거래량.
- 진입: 전일 종가 > 핸들 고점(피벗) AND 전일 거래량 ≥ 1.4 × 50일 평균 → 당일 시가 매수. 손절가(크기) = 핸들 저점. 청산: 종가 < 핸들 저점 OR 종가 < SMA(50)(사전 고정) OR 보유 상한 60거래일.
**B. VCP(일봉 근사)**
- Trend Template 7항(EPS 제외): 전일 종가 기준으로 모두 참.
- 최근 N(예 60~120)거래일에서 스윙 고점·저점 교대 추출(지그재그 임계 예 3%) → 연속 수축 폭 d1 > d2 > d3(각각 직전의 ≤ 75%), 마지막 폭 ≤ 10%, 마지막 구간 10일 평균 거래량 < 50일 평균의 70%.
- 진입: 전일 종가 > 마지막 수축 고점 AND 전일 거래량 ≥ 1.5 × 50일 평균. 손절가 = 마지막 수축 저점. 청산: 종가 < 손절가 OR 종가 < SMA(50) OR 상한 60거래일.
- 슬롯: 두 전략 모두 빈 슬롯 수만큼, 우선순위 = 돌파 강도(또는 52주 고점 근접도).

### 3.3 전략실 판단 (권고)
1. **지금 30종목·2016~2025로는 패턴 전략을 공정하게 검사할 수 없다**: (a) 생존편향이 패턴 전략에 가장 유리하게 작용(지금 시총 상위 = 과거 베이스 돌파 성공 종목) (b) 패턴 발생 수가 적어 C-2 미달 → "판단 불가" 예상.
2. 따라서 순서는 **유니버스 확장(코스피 200급, 가능하면 판정 시점 구성 목록) → 패턴 검출기(`tools/patterns.py`, 지표 라이브러리처럼 손계산 시험 포함) → R0~R5**. 유니버스 확장은 운영 세션에서 키움 ka10081 조회 승인(조회만)이 필요하다.
3. 검출기는 먼저 **기술(descriptive) 분석**으로: 30종목에서 2016~2025 사이 규칙 A·B에 걸리는 사건 수, 돌파 뒤 20·60거래일 수익 분포를 "전략"이 아니라 "사건 연구"로 본다(research/). 사건이 창당 10건 미달이면 전략화 보류.
4. 패턴 전략의 운영 리스크: 손절 7~8%는 종가 판정 + 갭이라 실제 손실이 더 크다. 보유 3·100만 원 한도에서는 어떤 패턴 전략도 결과가 L7에 묶인다(규모 실험 결론과 같음).

## 4. 사건 연구 결과 (2026-10-11, `research/event_study_patterns.py` → `2026-10-11-event-study-patterns.md`)
- 검출기 `tools/patterns.py`(손계산 시험 5 passed) 기본 파라미터, 30종목 2016~2025, 돌파 확인 다음 날 시가 진입, 비용 전.
- **컵앤핸들**: 사건 8건(연 0.8). +20일 중앙 −6.3%, +60일 중앙 −6.0%, 비용 초과 비율 25~38%. 2017년 4건·2022년 2건.
- **VCP**: 사건 14건(연 1.4). +20일 중앙 +5.0%(비용 초과 71%), +60일 중앙 −1.6%(평균 +10.2%는 012450 2024-02 +46.8% 한 건 영향). 손절 거리 중앙 12.6%로 넓다(수축 저점이 멀다 → 운영 7~8% 손절 룰과 어긋남).
- **결론**: 두 패턴 모두 **전략화 조건 미달**(사건 수 연 10건 기준의 1/10 수준). 30종목·엄격 규칙에서는 표본이 없다 — 규칙을 느슨하게 하면 사건은 늘지만 "데이터를 보고 규칙을 고르는" 행위라 하지 않았다. 유니버스 확장(코스피 200급·판정 시점 목록) 뒤 같은 사전 고정 규칙으로 재실행하는 것이 올바른 순서. 방향성(20일)은 VCP가 나아 재검토 1순위.
- 생존편향 주의: 이 표본은 패턴 전략에 가장 유리한데도 결과가 이 정도다 → 실제는 더 나쁠 가능성.

## 출처
- 컵앤핸들: [LuxAlgo cup-with-handle base](https://www.luxalgo.com/library/concept/cup-with-handle-base/), [Fidelity](https://fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/cup-with-handle), [StockAlarm guide](https://pro.stockalarm.io/blog/cup-and-handle-pattern-guide), [Capital.com](https://capital.com/en-ae/learn/technical-analysis/cup-and-handle-pattern), [ChartingLens](https://chartinglens.com/blog/cup-and-handle-pattern-guide), [StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/cup-with-handle)
- Bulkowski 통계: [thepatternsite.com/cup.html](https://thepatternsite.com/cup.html)
- VCP: [LuxAlgo VCP](https://www.luxalgo.com/library/concept/volatility-contraction-pattern/), [Minervini swing trading 체크리스트(2차)](https://skills.cat/skills/copyleftdev/sk1llz/minervini-swing-trading), [finermarketpoints VCP checklist(상용)](https://www.finermarketpoints.com/post/vcp-criteria-complete-checklist)
- 알고리즘 검출·백테스트 주장: [Wealth-Lab Semi-Cup(Siligardos)](https://wl6.wealth-lab.com/Strategy/Details/246), [TradingView Cup & Handle(Zeiierman)](https://pl.tradingview.com/scripts/chartpattern), [Sharpely VCP 스크리너(상용, 방법 미공개)](https://sharpely.in/blogs/volatility-contraction-pattern-vcp-rule-based-screener-built-high-quality/), [FinancialWisdom 상위 100 VCP(사후 선택)](https://www.financialwisdomtv.com/post/can-one-chart-pattern-beat-the-market-i-tested-the-top-100-stocks), [vcp-screener(오픈소스)](https://tessl.io/registry/skills/github/tradermonty/claude-trading-skills/vcp-screener)
- 미확인: Lo·Mamaysky·Wang(2000) 원문, O'Neil·Minervini 원저.

# 문헌 학습 노트 — 바소의 시장 판단·바인스타인 스테이지·트레일링/부분 익절 (2026-10-12)

웹 검색 1회씩, 2차 자료(원저 미확인). 목적: 사용자 규칙(r3-trend)의 **원전 의도 vs 전략실 근사**의 차이를 확인하고 v4(3R 익절 제거) 해석 기준을 세움.

## 1. 톰 바소 — "시장 판단"의 실체
- 검색된 자료에는 **이동평균 방향 필터가 바소의 규칙이라는 근거가 없다.** 바소의 핵심은 ① 추세추종(돌파 진입) ② **변동성 기반 사이징**: 초기 위험 0.5%/지분, 진행 중 1.0%, 21일 ATR 기준 변동성 노출 0.2~0.3%/지분, 포트폴리오 총위험 15~17% 상한 ③ 한도 초과 시 "일부 덜어내기(peel off)" ④ 출구는 지표로 강세에 파는 게 아니라 **스톱을 따라 올리다 걸려 나가기**.
- 반 타프 책의 "바소 설계 무작위 진입 시스템": 10일 EMA(ATR) × 3 초기 스톱, 종가 추적·불리하게는 안 움직임, 1% 위험 — 10개 시장 전부 수익(2차 전재).
- **우리 근사와의 차이**: 제가 "시장 판단"을 KOSPI > SMA200 + 기울기로 근사했는데, 바소식은 **시장 판단이 아니라 포지션 단위 변동성 관리**다. 즉 r3-trend의 REGIME-1은 사용자가 말한 "이동평균 위/아래"(사용자 본인 규칙)에는 맞지만 바소 요소는 **사이징·트레일에 반영해야** 한다 → 현재 S-3(위험 0.4%)·2R 뒤 ATR2 트레일은 방향이 같음. 추가 후보(사전 등록 뒤): 변동성 노출 상한(ATR21×수량/지분 ≤ 0.2~0.3%), 트레일을 **진입 즉시**(2R 뒤가 아니라) 3×ATR로 — 사용자 결정 ②("수익 극대화")와 일관.

## 2. 바인스타인 스테이지 — 사용자의 1→2→3 스테이지와 대응
- 원전 틀: **30주(≈150일) 이동평균**이 핵심. Stage 1 바닥 다지기(MA 평탄) → **Stage 2 상승**(MA 상승·가격 위, 저항 돌파 + 거래량 평균 이상 — 커뮤니티 임계 1.5~2배) → Stage 3 천장 → Stage 4 하락. 출구 = Stage 3 징후(30주선 하향 이탈·MA 평탄).
- 사용자의 "1차 상승 → 조정 → 새 상승"은 바인스타인 Stage 2 **안의 재돌파**(연속 베이스)에 해당. 제 근사(60일 고점 → 8~25% 조정 → 재돌파)는 그 축소판. 차이: 바인스타인은 **주간 차트·30주선 위**를 전제로 한다(사용자도 "주간 차트" 언급) → r3-trend에 "종가 > SMA150(≈30주)" 종목 조건을 넣으면 원전에 더 가깝다(현재는 지수 국면만 보고 종목 자체의 장기 추세는 안 봄). 사전 등록 뒤 v+1 후보.
- 거래량 임계 1.5~2배는 전부 커뮤니티 값 — 우리 1.5배도 같은 수준(원전 수치 아님).

## 3. 트레일링 스톱 vs 고정 익절 · 부분 익절
- **직접 비교한 엄격한 연구는 검색에서 못 찾음.** 실무 합의: 추세추종은 트레일(목표가가 오른쪽 꼬리를 자름), 평균회귀는 목표가. 샹들리에 출구 = 최근 N(22)일 최고 − 3×ATR(22).
- 우리 자체 결과와 연결: T2-v3 공정 기준선 연구에서 "청산 규칙은 보유 기간 선택일 뿐"(초과 ≈ 0) — 따라서 v4의 "3R 익절 제거"는 **평균을 올리기보다 분포 꼬리를 오른�ose로 넓히는 선택**이고, 사용자 선호(승률 ↓·수익 ↑)와 일치. 결과가 평균 R에서 v3과 비슷하고 상위 10%만 커지면 "예상대로".
- 샹들리에(최고 − 3×ATR22)는 우리 트레일(피크 − 2×ATR14)보다 넓다. T2-v2에서 ATR3이 ATR2보다 꼬리가 나빴지만 그건 **진입 즉시 추적**의 경우 — 2R 뒤 추적은 미시험. 사전 등록 뒤 비교 가능.

## 4. 이 학습이 바꾸는 것(규칙 변경 아님 — 다음 사전 등록 후보 목록)
1. r3-trend v5 후보: 종목 조건 "종가 > SMA150"(바인스타인 30주선) 추가 → 거래 수 감소 예상(이미 56건).
2. 바소식 변동성 노출 상한(ATR21×수량 ≤ 지분 0.3%) — 현재 L7 100만 원이 더 작아 지금은 무효, 규모 확대 뒤 의미.
3. 트레일 변형: 2R 뒤 2×ATR14 vs 진입 즉시 3×ATR(바소/타프) — v4 결과 뒤.
4. "시장 판단"은 사용자 규칙(이평 위/아래)으로 유지; 바소를 근거로 쓰지 않는다(문서 수정: ideas 카드 표의 "바소" 표기를 "사용자 규칙 + 바소는 사이징·트레일에 반영"으로).

## 출처
- 바소: [Stockbsessed Q&A](https://stockbsessed.substack.com/p/11-questions-with-market-wizard-tom), [TurtleTrader 소개](https://www.turtletrader.com/trader-basso/), [ForexFactory(반 타프 책 전재)](https://www.forexfactory.com/thread/post/231380), [Wikipedia trend following](https://en.wikipedia.org/wiki/Trend_following)
- 바인스타인: [MQL5 Stage Analysis 구현](https://www.mql5.com/en/articles/22746), [LuxAlgo Weinstein Stage Analysis](https://www.luxalgo.com/library/indicator/weinstein-stage-analysis/), [TradingView Stage 2 예시](https://in.tradingview.com/chart/DIVISLAB/jofJTfN1-DIVISLAB-Stage-2-Breakout/)
- 출구: [LuxAlgo Trailing Method Taxonomy](https://www.luxalgo.com/library/concept/trailing-method-taxonomy.md), [LuxAlgo Chandelier Exit](https://www.luxalgo.com/library/indicator/chandelier-exit/), [Chandelier Exit 해설](https://karenwong.substack.com/p/chandelier-exit)
- 미확인: 바소·바인스타인·타프 원저.

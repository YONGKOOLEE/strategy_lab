# 새 기준선 — 운영 연구 프로필 + 배분 규칙 (사전 등록 2026-10-13 17:27, Bash date)

운영 CP-034(A-092~094) 이후 첫 측정. legacy 결과와 비교하지 않고 이후 튜닝의 기준선으로 쓴다.
- 공통: `--limits C:\AI\trading_system\trading_system\config\limits.research.toml`(L1 0.5%+여유 3%, L7 10% 비율, L4 2%), 배분 규칙 `candidates.regime_kospi.strategy:RegimeKospiV1`(SMA200·기울기 20, 사전 고정), 지수 data/index/001.csv. 전략 내장 국면 필터는 끈다(regime_n 0) — 국면은 배분 규칙만 담당.
- 실행 1: rs-momentum v4 코드, params regime_n 0, 200종목.
- 실행 2: r3-trend v6 코드, B 프로필 + regime_n 0, turnover30, U-B.
- 판정: 운영 판정표 그대로 기록(전략 C-1~C-8 + 배분 Q-9 ①②③). 지수 결측 1회 → 판단 불가. 결과를 보고 값을 바꾸지 않는다. 내장 필터 결과(legacy)와는 "방향 일치"만 확인.

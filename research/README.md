# 자유 분석

- 데이터는 `..\data\daily\<종목코드>.csv` (열: date,open,high,low,close,volume — 수정주가, 2025-12-31까지).
- 운영 `.venv` 파이썬(`C:\AI\trading_system\trading_system\.venv\Scripts\python.exe`)에는 표준 라이브러리와 운영 패키지만 있다. pandas·노트북이 필요하면 전략실 전용 가상환경을 따로 만든다 — 설치 전에 목적·영향을 설명하고 승인받는다(CLAUDE.md §2).
- 여기서 나온 수치는 비용·체결 가정이 운영 검증 실행기와 다를 수 있다. 후보로 올릴 때는 `tools\validate.ps1`로 다시 본다.

# 규모 실험용 파라미터 파일 규칙

> **2026-10-11 13:25 갱신**: `order_cap` ParamSpec 상한을 계좌 L7(1,000,000)로 내렸다(critic — 상한을 넘는 ±20% 변형이 게이트 전부 거부로 C-4를 구조적으로 미충족시킴). 따라서 `params-*-scale-cap10m.toml`(order_cap 1,000만)은 현재 **범위 밖 → 적재 거부**된다. 규모 실험을 다시 하려면 후보 폴더에 `scale/strategy.py` 사본(ParamSpec 상한만 올린 연구용)을 두고 그 클래스로 quick을 돌린다 — 운영 인계 대상 아님. 2026-10-11의 규모 실험 결과(notes.md)는 그 전 코드로 얻은 것이라 유효.

후보마다 `params-v<n>-scale-cap10m.toml`(기본값 + `order_cap = "10000000"`)을 두고, `research/limits-scale-test-l1fix.toml`과 함께 quick `--params`·`--limits`로 돌린다. 라벨은 `scaleB`. 결과는 "사용자 미결정 한도 가정·L1 2% 임시 보정"으로 표시하며 폐기 판정에는 쓰지 않는다(판정은 운영 한도 base 실행).

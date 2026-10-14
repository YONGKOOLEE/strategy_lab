"""1차 선별기 — 후보를 운영 백테스트 엔진(`trading_system.app.backtest.run_backtest`)으로 **창 1~2개만** 빨리 돌려
거래당 기대값·거래 수를 본다. 검증 실행기(validate.ps1, 91회·약 86분)에 넣을 가치가 있는지 먼저 거르는 용도다.

- 운영 저장소는 읽기와 import만 한다(쓰기 0). 결과는 전략실 `results/quick/<날짜>-<후보>-v<n>-<라벨>/`.
- 체결·비용·한도·달력·슬리피지(% 방식, 기본 0.1%)는 검증 실행기와 같은 설정(`config/market.backtest.toml`·`limits.backtest.toml`·
  `validation.toml`)을 그대로 읽는다. 다른 것은 창 수와 변형 유무뿐이다.
- 2026-01-01 이후(최종 확인 구간)는 엔진이 거부한다(D-163). 창은 검증 실행기와 같은 7개(k=1..7 = 검증 2019~2025) 중 고른다.
- 실행마다 `candidates/<후보>/trials.jsonl`에 한 줄을 덧붙인다(시도 횟수 장부 — 파라미터를 몇 번 바꿔 봤는지 남긴다. 지우지 않는다).

- `--train`(학습 창 모드, HANDOFF §5 ③): 창 k의 **학습 구간**(D-162, k=1 → 2016~2018)을 실행 구간으로 쓴다. 파라미터는 여기서 고르고
  검증 창(2019~2025)은 판정에만 쓴다. `--train-start/--train-end`로 학습 구간 안쪽만 잘라 쓸 수 있다 — 데이터가 2016-01-04부터라
  지표 워밍업(SMA200 등)이 2016년을 먹으므로, 파라미터끼리 비교할 때는 공통 시작일(예 2017-01-01)을 사전 등록해 맞춘다.
  학습 창 결과는 파라미터 선택용이며 폐기·통과 판정이 아니다. 장부에는 tool="quick-train"으로 남는다.

실행: tools\\quick.ps1 -Candidate <폴더> -Class <클래스> -Version <n> [-Windows 4,7] [-Label base]
      tools\\quick.ps1 … -Train [-Windows 1] [-TrainStart 2017-01-01] -Label train-mom90 -Params <파일>
"""

from __future__ import annotations

import argparse
import json
import sys
import time as _time
from dataclasses import replace
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
OPS_DEFAULT = Path(r"C:\AI\trading_system\trading_system")
_Q2 = Decimal("0.01")


def _fmt(x: Decimal | None) -> str:
    return "—" if x is None else format(x.quantize(_Q2, rounding=ROUND_HALF_UP), "f")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="quick.py")
    p.add_argument("--candidate", required=True)
    p.add_argument("--cls", required=True)
    p.add_argument("--version", type=int, required=True)
    p.add_argument("--windows", default=None, help="창 k 목록(쉼표). 기본 4,7 = 2022(하락)·2025, --train이면 기본 1 = 학습 2016~2018")
    p.add_argument("--train", action="store_true", help="창 k의 학습 구간을 실행(파라미터 선택용, 판정 아님)")
    p.add_argument("--train-start", default=None, help="학습 구간 시작일 YYYY-MM-DD(학습 구간 안쪽만, 워밍업 공통화용)")
    p.add_argument("--train-end", default=None, help="학습 구간 종료일 YYYY-MM-DD(학습 구간 안쪽만)")
    p.add_argument("--label", default="base", help="실행 라벨(결과 폴더·장부에 기록). 파라미터를 바꿨으면 라벨도 바꾼다")
    p.add_argument("--eval-time", default="09:30")
    p.add_argument("--cash", default="100000000")
    p.add_argument("--slippage-pct", default=None, help="기본은 운영 validation.toml slippage_base(0.001)")
    p.add_argument("--params", default=None,
                   help="파라미터 파일 경로 지정(기본 candidates/<후보>/params-v<n>.toml). 대조군·변형 실험용 — 라벨을 반드시 바꾼다")
    p.add_argument("--data", default=None,
                   help="일봉 폴더 지정(기본 data/daily). 모드 2(사용자 목록) 시험용 data/lists/<이름>/ — 라벨을 바꾼다")
    p.add_argument("--limits", default=None,
                   help="계좌 한도 파일 지정(기본 운영 config/limits.backtest.toml). 전략실 사본으로 규모 실험 — 결과는 '사용자 미결정 한도 가정'")
    p.add_argument("--ops", default=str(OPS_DEFAULT))
    ns = p.parse_args(argv)

    ops = Path(ns.ops)
    sys.path.insert(0, str(ops / "src"))
    sys.path.insert(0, str(LAB))
    from trading_system.app.backtest import BacktestConfig, BacktestError
    from trading_system.app.main import _load_common, load_daily_csv
    from trading_system.app.validation import ValidationError, Window, run_window, walkforward_windows
    from trading_system.app.validation_tool import _git_commit, extend_calendar, load_validation_settings
    from trading_system.app.wiring import load_strategy
    from trading_system.config.app_file import StrategyDeploy
    from trading_system.config.errors import ConfigError
    from trading_system.config.limits_file import load_limits_file
    from trading_system.domain.enums import Mode
    from trading_system.domain.market import InstrumentInfo, InstrumentKind

    folder = LAB / "candidates" / ns.candidate
    params_path = Path(ns.params) if ns.params else folder / f"params-v{ns.version}.toml"
    if (ns.params or ns.limits or ns.data) and ns.label == "base":
        print("--params/--limits/--data를 지정하면 라벨도 바꿔야 한다(-Label), 기준 실행과 섞이지 않게")
        return 2
    limits_path = Path(ns.limits) if ns.limits else ops / "config" / "limits.backtest.toml"
    data_dir = Path(ns.data) if ns.data else LAB / "data" / "daily"
    hol = LAB / "data" / "holidays-2016-2023.json"
    for f in (params_path, data_dir, hol):
        if not f.exists():
            print(f"없음: {f} (데이터는 tools\\sync-data.ps1 먼저)")
            return 2
    if (ns.train_start or ns.train_end) and not ns.train:
        print("--train-start/--train-end는 --train과 함께만 쓴다")
        return 2
    ks = [int(x) for x in (ns.windows or ("1" if ns.train else "4,7")).split(",") if x.strip()]
    windows = {w.k: w for w in walkforward_windows()}
    if any(k not in windows for k in ks):
        print(f"창 번호는 1~7만: {ks}")
        return 2
    if ns.train:  # 실행 구간 = 학습 구간(안쪽으로만 자를 수 있음). 검증 구간은 건드리지 않는다
        for k in ks:
            w0 = windows[k]
            s = date.fromisoformat(ns.train_start) if ns.train_start else w0.train_start
            e = date.fromisoformat(ns.train_end) if ns.train_end else w0.train_end
            if not (w0.train_start <= s <= e <= w0.train_end):
                print(f"창 {k} 학습 구간은 {w0.train_start}~{w0.train_end} — 지정 {s}~{e}는 밖이거나 순서가 틀림")
                return 2
            windows[k] = Window(k, w0.train_start, w0.train_end, s, e)

    started = _time.monotonic()
    try:
        settings = load_validation_settings(ops / "config" / "validation.toml")
        gate_settings, _, calendar, ticks, caps = _load_common(ops, Mode.BACKTEST)
        calendar = extend_calendar(calendar, hol, "일봉 추출 휴장일(전략실 quick)")
        limits = load_limits_file(limits_path).limits
        strat, params = load_strategy(StrategyDeploy(f"candidates.{ns.candidate}.strategy:{ns.cls}", params_path.resolve(), ()))
        data = {f.stem: load_daily_csv(f) for f in sorted(data_dir.glob("*.csv"))}
        if not data:
            raise ConfigError("데이터 CSV가 없음")
        strat.spec = replace(strat.spec, universe=tuple(sorted(data)))  # type: ignore[misc]  # 유니버스 = 데이터 폴더(실행 객체만)
        infos = {c: InstrumentInfo(c, InstrumentKind.STOCK, Decimal("1"), Decimal("1")) for c in data}
        hh, mm = ns.eval_time.split(":")
        et = time(int(hh), int(mm))
        mode = "-train" if ns.train else ""
        out_dir = LAB / "results" / "quick" / f"{date.today():%Y%m%d}-{ns.candidate}-v{ns.version}{mode}-{ns.label}"
        if out_dir.exists():
            print(f"결과 폴더가 이미 있음(라벨을 바꾼다): {out_dir}")
            return 2
        slip = Decimal(ns.slippage_pct) if ns.slippage_pct else settings["slippage_base"]
        template = BacktestConfig(
            run_id="template", strategy=strat, params=params, caps=caps, account_limits=limits,
            gate_settings=gate_settings, calendar=calendar, ticks=ticks, slippage_tick=Decimal("10"),
            data=data, infos=infos, start=date(1900, 1, 1), end=date(1900, 1, 1), initial_cash=Decimal(ns.cash),
            out_dir=out_dir, eval_time=et, eval_times=(et,), data_version=f"csv:{data_dir.name}",
            code_commit=_git_commit(ops), final_from=settings["final_from"])  # type: ignore[arg-type]

        rows = []
        all_trades = []
        for k in ks:
            w = windows[k]
            res = run_window(template, w, label=ns.label, out_dir=out_dir, slippage_pct=slip)  # type: ignore[arg-type]
            pnl = sum((t.pnl for t in res.trades), Decimal("0"))
            exp = pnl / len(res.trades) if res.trades else None
            wins = sum(1 for t in res.trades if t.pnl > 0)
            rows.append({"k": k, "val": f"{w.val_start}~{w.val_end}", "trades": len(res.trades),
                         "expectancy": _fmt(exp), "win_rate": _fmt(Decimal(wins) / len(res.trades) * 100) if res.trades else "—",
                         "total_return": res.metrics.get("total_return"), "mdd": res.metrics.get("max_drawdown"),
                         "signals": len(res.signals), "rejects": dict(res.rejects), "quality_fail": len(res.quality_failures)})
            all_trades += res.trades
    except (ConfigError, BacktestError, ValidationError, ValueError, OSError) as exc:
        print(f"실행 거부: {type(exc).__name__}: {exc}")
        return 2

    pooled_pnl = sum((t.pnl for t in all_trades), Decimal("0"))
    pooled_exp = pooled_pnl / len(all_trades) if all_trades else None
    elapsed = round(_time.monotonic() - started, 1)

    print(f"\n== quick{' [학습 창]' if ns.train else ''}: {strat.spec.strategy_id} v{ns.version} [{ns.label}] 슬리피지 {slip} 판정 {ns.eval_time} ==")
    print(f"운영 코드 {template.code_commit} · 호가 표 {'있음(호가 단위 맞춤)' if ticks is not None else '없음(1원 맞춤)'} "
          f"— 운영 설정이 바뀌면 같은 전략도 수치가 달라진다. 비교는 같은 운영 코드끼리.")
    print(f"한도 파일 {limits_path.name} · L1 {limits.l1_max_loss_ratio} L2 {limits.l2_max_symbol_ratio} "
          f"L6 {limits.l6_max_positions} L7 {limits.l7_max_order_amount}"
          + ("  ⚠ 전략실 사본 — 사용자 미결정 한도 가정" if ns.limits else " (운영 승인값 A-034)"))
    print(f"창 | {'학습 구간' if ns.train else '검증 구간'} | 거래 | 거래당 기대값(원) | 승률% | 총수익률 | MDD | 신호 | 거부 | 품질실패")
    for r in rows:
        print(f"{r['k']} | {r['val']} | {r['trades']} | {r['expectancy']} | {r['win_rate']} | {r['total_return']} | {r['mdd']} | "
              f"{r['signals']} | {r['rejects']} | {r['quality_fail']}")
    print(f"합산 | 거래 {len(all_trades)} | 거래당 기대값 {_fmt(pooled_exp)}원 | 시간 {elapsed}초")
    if ns.train:
        by_year: dict[int, list[Decimal]] = {}
        for t in all_trades:
            by_year.setdefault(t.exit_day.year, []).append(t.pnl)
        print("학습 구간 연도별(청산일 기준) | 거래 | 거래당 기대값(원)")
        for y in sorted(by_year):
            print(f"  {y} | {len(by_year[y])} | {_fmt(sum(by_year[y], Decimal('0')) / len(by_year[y]))}")
        first = min((t.entry_day for t in all_trades), default=None)
        print(f"첫 진입일 {first or '—'} — 늦으면 워밍업이 구간을 먹은 것. 파라미터끼리 비교는 같은 --train-start로.")
        print("학습 창 결과: 파라미터 선택용(사전 등록한 선택 규칙으로 고름). 폐기·통과 판정 아님 — 판정은 검증 창(validate.ps1).")
    else:
        verdict = "폐기 후보(기대값 ≤ 0)" if pooled_exp is None or pooled_exp <= 0 else "검증 실행기 투입 검토(기대값 > 0 — 아직 C-3·C-4 미검사)"
        print(f"1차 판단: {verdict}")
    print("주의: 생존편향 포함(과대 추정), 창 2개는 표본이 작다. 공식 기준은 7개 창 합산 ≥ 100건·슬리피지 2배·±20% 변형(validate.ps1).")
    print(f"결과 폴더: {out_dir}")

    ledger = folder / "trials.jsonl"
    rec = {"at": datetime.now().isoformat(timespec="seconds"), "tool": "quick-train" if ns.train else "quick",
           "version": ns.version, "label": ns.label, "windows": ks,
           "ranges": {k: f"{windows[k].val_start}~{windows[k].val_end}" for k in ks}, "params": {k: str(v) for k, v in params.items()}, "slippage_pct": str(slip),
           "ops_commit": template.code_commit, "tick_table": ticks is not None, "params_file": params_path.name,
           "limits_file": limits_path.name, "limits": {"l1": str(limits.l1_max_loss_ratio), "l2": str(limits.l2_max_symbol_ratio),
                                                      "l6": limits.l6_max_positions, "l7": str(limits.l7_max_order_amount)},
           "trades": len(all_trades), "expectancy": _fmt(pooled_exp), "per_window": rows, "seconds": elapsed}
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    n_trials = sum(1 for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())
    print(f"시도 장부: {ledger} (누적 {n_trials}회 — 많아질수록 결과가 우연히 좋을 확률이 커진다)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

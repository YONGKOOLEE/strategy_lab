"""운영 M2 백테스트 실행기(app.backtest_m2.run_backtest_m2)로 전략실 코인 후보를 돌린다. 운영 저장소는 읽기·import만.

- 데이터: data/crypto/<심볼>-1d.csv(전략실 사본, 2025-12-31까지). 규칙: 바이낸스 BTCUSDT 테스트넷 확인값(binance-spot.md):
  tick 0.01·step 0.00001·최소 수량 0.00001·최소 주문 5 USDT. 수수료 0.1%(예시 요율)·매도세 0, 슬리피지 --slip(기본 0.0005).
- 한도: 운영 M2 PAPER 한도(A-064: L1 0.5%·L2 10%·L3 50%·L4 1%·L7 100 USDT)는 위험 5% 후보를 막는다 → 기본은 **전략실 가정 한도**
  (L1 6%·L2 100%·L3 100%·L4 --l4·L5 5·L6 1·L7 무제한). `--ops-limits`면 운영 PAPER 한도 그대로(축소 운영 확인용).
- 결과: results/m2/<날짜>-<후보>-<라벨>/ (엔진 산출물) + 표준출력 요약. 판정 아님(연구 참고).
실행: <운영 .venv python> tools/m2_quick.py --candidate btc_trend --cls BtcTrendV1 --version 1 [--label base] [--start 2017-09-01] [--end 2025-12-31]
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
OPS = Path(r"C:\AI\trading_system\trading_system")
D = Decimal


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--cls", required=True)
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--params", default=None)
    ap.add_argument("--label", default="base")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start", default="2017-09-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--cash", default="10000")
    ap.add_argument("--slip", default="0.0005")
    ap.add_argument("--fee", default="0.001")
    ap.add_argument("--l4", default="0.30", help="가정 한도의 일일 손실 정지 비율(기본 30%% — 사실상 끔, 미결정)")
    ap.add_argument("--l1", default="0.06", help="가정 한도 L1 1회 최대 손실 비율(기본 6%%)")
    ap.add_argument("--l2", default="1.0", help="가정 한도 L2 종목 비중")
    ap.add_argument("--l3", default="1.0", help="가정 한도 L3 총 노출")
    ap.add_argument("--l7", default="1000000000", help="가정 한도 L7 1회 주문 최대(USDT)")
    ap.add_argument("--module", default=None, help="전략 모듈 경로(기본 candidates.<candidate>.strategy:<cls>) — 연구용 사본")
    ap.add_argument("--lot-step", default="0.00001", help="수량 단위(BTCUSDT 0.00001, ETHUSDT 0.0001 가정)")
    ap.add_argument("--ops-limits", action="store_true", help="운영 M2 PAPER 한도(config/m2/limits.paper.toml) 사용")
    return ap


def main(argv: list[str]) -> int:
    ns = parser().parse_args(argv)
    if date.fromisoformat(ns.end) >= date(2026, 1, 1):
        print("2026 이후는 최종 확인 구간 — 쓰지 않는다")
        return 2
    out = LAB / "results" / "m2" / f"{date.today():%Y%m%d}-{ns.candidate}-{ns.label}"
    if out.exists():
        print(f"이미 있음(라벨 변경): {out}")
        return 2
    res, cfg, lim_note, strat = run_engine(ns, out)
    eq = res.equity
    print(f"== M2 엔진: {strat.spec.strategy_id} v{ns.version} [{ns.label}] {ns.start}~{ns.end} · {lim_note}")
    print(f"거래 {len(res.trades)} · 최종 {eq[-1][1]:,.2f} USDT ({eq[-1][1] / D(ns.cash) - 1:+.1%}) · 지표 {dict((k, res.metrics[k]) for k in ('max_drawdown', 'win_rate', 'total_return') if k in res.metrics)}")
    print(f"게이트 거부 {dict(res.rejects)} · K2 {res.k2_resumes} · 결과 {out}")
    return 0


def run_engine(ns: argparse.Namespace, out: Path):  # type: ignore[no-untyped-def]
    """운영 M2 엔진 1회 실행. ns = main()의 인자(다른 스크립트는 parse_args로 만들어 넘김). 반환 (결과, 설정, 한도 설명, 전략)."""
    if date.fromisoformat(ns.end) >= date(2026, 1, 1):
        raise ValueError("2026 이후는 최종 확인 구간")
    sys.path.insert(0, str(OPS / "src"))
    sys.path.insert(0, str(LAB))
    from trading_system.app.backtest_m2 import SpotBacktestConfig, render_report_m2, run_backtest_m2
    from trading_system.app.wiring import load_strategy
    from trading_system.config.app_file import StrategyDeploy
    from trading_system.config.limits_file import load_limits_file
    from trading_system.domain.limits import AccountLimits
    from trading_system.domain.market import CostRates
    from trading_system.domain.strategy import Bar
    from trading_system.domain.trading_rules import SymbolRules

    folder = LAB / "candidates" / ns.candidate
    params_path = Path(ns.params) if ns.params else folder / f"params-v{ns.version}.toml"
    strat, params = load_strategy(StrategyDeploy(ns.module or f"candidates.{ns.candidate}.strategy:{ns.cls}", params_path.resolve(), ()))
    rows = []
    with (LAB / "data" / "crypto" / f"{ns.symbol}-1d.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(Bar(date.fromisoformat(r["date"]), D(r["open"]), D(r["high"]), D(r["low"]), D(r["close"]), D(r["volume"])))
    rules = SymbolRules(instrument=ns.symbol, tick_size=D("0.01"), min_price=D("0.01"), max_price=D("1000000"),
                        lot_min_qty=D(ns.lot_step), lot_max_qty=D("9000"), lot_step=D(ns.lot_step), market_min_qty=D(ns.lot_step),
                        market_max_qty=D("9000"), market_step=D(ns.lot_step), min_notional=D("5"), max_notional=None,
                        apply_min_to_market=True, apply_max_to_market=False)
    if ns.ops_limits:
        limits = load_limits_file(OPS / "config" / "m2" / "limits.paper.toml", market="M2").limits
        lim_note = "운영 M2 PAPER 한도(A-064)"
    else:
        limits = AccountLimits(l1_max_loss_ratio=D(ns.l1), l2_max_symbol_ratio=D(ns.l2), l3_max_total_ratio=D(ns.l3),
                               l4_daily_loss_ratio=D(ns.l4), l5_daily_new_orders=5, l6_max_positions=1,
                               l7_max_order_amount=D(ns.l7), l10_leverage_total_ratio=None, warn_usage_ratio=D("0.80"),
                               order_window_start=time(0, 10), order_window_end=time(23, 50), daily_reference_time=time(0, 0),
                               report_time=time(0, 10))
        lim_note = f"전략실 가정 한도(미결정): L1 {ns.l1}·L2 {ns.l2}·L3 {ns.l3}·L4 {ns.l4}·L7 {ns.l7}"
    out.mkdir(parents=True, exist_ok=True)
    cfg = SpotBacktestConfig(
        run_id=f"{ns.candidate}-{ns.label}", strategy=strat, params=params, account_limits=limits, rules={ns.symbol: rules},
        pairs={ns.symbol: (ns.symbol[:-4], ns.symbol[-4:])},
        cost_rates=CostRates(commission_rate=D(ns.fee), sell_tax_rate=D("0"), cost_quantum=D("0.00000001")),
        data={ns.symbol: rows}, start=date.fromisoformat(ns.start), end=date.fromisoformat(ns.end),
        initial_cash=D(ns.cash), out_dir=out, slippage=D(ns.slip), data_version=f"csv:{ns.symbol}-1d")
    res = run_backtest_m2(cfg)
    (out / "report.md").write_text(render_report_m2(cfg, res, reproducible=None, lookahead_bad=None), encoding="utf-8")
    return res, cfg, lim_note, strat

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

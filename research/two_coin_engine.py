"""J. BTC+ETH 한 계좌(종목별 위험 2.5%·상한 49%)를 운영 M2 엔진(app.backtest_m2)으로 — 정보·도구 확인. 판정 아님.
사전 등록: research/2026-10-18-overnight-design.md J. 운영 코드는 import·실행만(쓰기 없음), 결과는 results/m2/.
"""

from __future__ import annotations

import csv
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
OPS = Path(r"C:\AI\trading_system\trading_system")
sys.path.insert(0, str(OPS / "src"))
sys.path.insert(0, str(LAB))
D = Decimal

from trading_system.app.backtest_m2 import SpotBacktestConfig, run_backtest_m2  # noqa: E402
from trading_system.app.wiring import load_strategy  # noqa: E402
from trading_system.config.app_file import StrategyDeploy  # noqa: E402
from trading_system.domain.limits import AccountLimits  # noqa: E402
from trading_system.domain.market import CostRates  # noqa: E402
from trading_system.domain.strategy import Bar  # noqa: E402
from trading_system.domain.trading_rules import SymbolRules  # noqa: E402

STEPS = {"BTCUSDT": "0.00001", "ETHUSDT": "0.0001"}


def bars(sym: str) -> list:
    with (LAB / "data" / "crypto" / f"{sym}-1d.csv").open(encoding="utf-8") as f:
        return [Bar(date.fromisoformat(r["date"]), D(r["open"]), D(r["high"]), D(r["low"]), D(r["close"]), D(r["volume"])) for r in csv.DictReader(f)]


def rules(sym: str) -> SymbolRules:
    st = D(STEPS[sym])
    return SymbolRules(instrument=sym, tick_size=D("0.01"), min_price=D("0.01"), max_price=D("1000000"), lot_min_qty=st, lot_max_qty=D("9000"),
                       lot_step=st, market_min_qty=st, market_max_qty=D("9000"), market_step=st, min_notional=D("5"), max_notional=None,
                       apply_min_to_market=True, apply_max_to_market=False)


def run_crypto_trend(paper: bool) -> None:
    """crypto-trend strategy.py를 운영 엔진(하루 1회 00:15 판정)에서 적재·실행 — 호환성 확인용(60분 판정 결과 아님)."""
    from trading_system.config.limits_file import load_limits_file
    pfile = LAB / "candidates" / "crypto_trend" / ("params-v1-paper.toml" if paper else "params-v1.toml")
    strat, params = load_strategy(StrategyDeploy("candidates.crypto_trend.strategy:CryptoTrendV1", pfile.resolve(), ()))
    if paper:
        lim = load_limits_file(OPS / "config" / "m2" / "limits.paper.toml", market="M2").limits
    else:
        lim = AccountLimits(l1_max_loss_ratio=D("0.0275"), l2_max_symbol_ratio=D("0.50"), l3_max_total_ratio=D("1.0"), l4_daily_loss_ratio=D("0.30"),
                            l5_daily_new_orders=5, l6_max_positions=2, l7_max_order_amount=D("1000000000"), l10_leverage_total_ratio=None,
                            warn_usage_ratio=D("0.80"), order_window_start=time(0, 10), order_window_end=time(23, 50),
                            daily_reference_time=time(0, 0), report_time=time(0, 10))
    out = LAB / "results" / "m2" / f"{date.today():%Y%m%d}-crypto-trend-daily-{'paper' if paper else 'v1'}"
    cfg = SpotBacktestConfig(run_id=f"crypto-trend-{'paper' if paper else 'v1'}", strategy=strat, params=params, account_limits=lim,
                             rules={s: rules(s) for s in STEPS}, pairs={s: (s[:-4], s[-4:]) for s in STEPS},
                             cost_rates=CostRates(commission_rate=D("0.001"), sell_tax_rate=D("0"), cost_quantum=D("0.00000001")),
                             data={s: bars(s) for s in STEPS}, start=date(2017, 9, 1), end=date(2025, 12, 31), initial_cash=D("10000"), out_dir=out,
                             slippage=D("0.0005"), data_version="csv:BTCUSDT+ETHUSDT-1d")
    res = run_backtest_m2(cfg)
    eq = res.equity
    by = {s: sum(1 for t in res.trades if t.instrument == s) for s in STEPS}
    print(f"  crypto-trend {'PAPER 축소판·A-064 한도' if paper else 'v1·가정 한도'} (엔진 하루 1회 판정 — 호환성 확인): 거래 {len(res.trades)} {by} · "
          f"{eq[-1][1] / D(10000) - 1:+.1%} · MDD {res.metrics.get('max_drawdown')} · 거부 {dict(res.rejects)}")


def main() -> int:
    if sys.argv[1:] == ["crypto-trend"]:
        run_crypto_trend(False)
        run_crypto_trend(True)
        return 0
    out_root = LAB / "results" / "m2" / f"{date.today():%Y%m%d}-two-coin"
    params_path = out_root / "params.toml"
    out_root.mkdir(parents=True, exist_ok=True)
    params_path.write_text('strategy = "two-coin-probe"\nversion = 1\n\n[params]\nentry_n = 25\nexit_n = 50\nstop_atr = "2"\nrisk_ratio = "0.025"\n'
                           'max_weight = "0.49"\norder_cap = "1000000000"\n', encoding="utf-8")
    strat, params = load_strategy(StrategyDeploy("research.two_coin_probe_strategy:TwoCoinProbe", params_path.resolve(), ()))
    data = {s: bars(s) for s in STEPS}
    print("J. BTC+ETH 한 계좌(위험 2.5%·상한 49%) 운영 M2 엔진 2017-09-01~2025-12-31 · 가정 한도(미승인) · 판정 아님")
    for l1 in ("0.025", "0.0275", "0.03"):
        lim = AccountLimits(l1_max_loss_ratio=D(l1), l2_max_symbol_ratio=D("0.50"), l3_max_total_ratio=D("1.0"), l4_daily_loss_ratio=D("0.30"),
                            l5_daily_new_orders=5, l6_max_positions=2, l7_max_order_amount=D("1000000000"), l10_leverage_total_ratio=None,
                            warn_usage_ratio=D("0.80"), order_window_start=time(0, 10), order_window_end=time(23, 50),
                            daily_reference_time=time(0, 0), report_time=time(0, 10))
        out = out_root / f"l1-{l1}"
        if out.exists():
            print(f"  이미 있음: {out}")
            continue
        cfg = SpotBacktestConfig(run_id=f"two-coin-l1-{l1}", strategy=strat, params=params, account_limits=lim,
                                 rules={s: rules(s) for s in STEPS}, pairs={s: (s[:-4], s[-4:]) for s in STEPS},
                                 cost_rates=CostRates(commission_rate=D("0.001"), sell_tax_rate=D("0"), cost_quantum=D("0.00000001")),
                                 data=data, start=date(2017, 9, 1), end=date(2025, 12, 31), initial_cash=D("10000"), out_dir=out,
                                 slippage=D("0.0005"), data_version="csv:BTCUSDT+ETHUSDT-1d")
        res = run_backtest_m2(cfg)
        eq = res.equity
        by = {s: sum(1 for t in res.trades if t.instrument == s) for s in STEPS}
        print(f"  L1 {l1}: 거래 {len(res.trades)} {by} · 최종 {eq[-1][1]:,.0f} ({eq[-1][1] / D(10000) - 1:+.1%}) · MDD {res.metrics.get('max_drawdown')} · 거부 {dict(res.rejects)} · K2 {res.k2_resumes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Quick A/B test: compare 4h MTF condition
  A) EMA20 > EMA50  (current — lagging crossover)
  B) price > EMA50  (proposed — faster confirmation)

Run: python test_4h_mtf.py
"""
import types
from backtest import WalkForwardBacktester
from agents import TechnicalAgent

print("Fetching 730 days of data (shared across both runs)...")
bt    = WalkForwardBacktester()
df    = bt.fetch_historical(days=730, timeframe="1h")
df_4h = bt.fetch_historical(days=730, timeframe="4h")
print(f"Fetched {len(df)} 1h candles, {len(df_4h)} 4h candles.\n")


def run(label: str, use_price_vs_ema50: bool):
    # Patch _check_4h_alignment on TechnicalAgent
    if use_price_vs_ema50:
        def _check(df_4h, signal):
            import pandas as pd
            close_4h = df_4h["close"]
            ema50_4h = close_4h.ewm(span=50, adjust=False).mean()
            if signal == "BUY":
                return float(close_4h.iloc[-1]) > float(ema50_4h.iloc[-1])
            else:
                return float(close_4h.iloc[-1]) < float(ema50_4h.iloc[-1])
    else:
        def _check(df_4h, signal):
            close_4h = df_4h["close"]
            ema20_4h = close_4h.ewm(span=20, adjust=False).mean()
            ema50_4h = close_4h.ewm(span=50, adjust=False).mean()
            if signal == "BUY":
                return float(ema20_4h.iloc[-1]) > float(ema50_4h.iloc[-1])
            else:
                return float(ema20_4h.iloc[-1]) < float(ema50_4h.iloc[-1])

    TechnicalAgent._check_4h_alignment = staticmethod(_check)
    bt.technical = TechnicalAgent()

    print(f"{'─'*50}")
    print(f"  {label}")
    print(f"{'─'*50}")
    result = bt.run(df, df_4h=df_4h)
    print(f"  Sharpe:        {result.sharpe_ratio:.3f}")
    print(f"  Total return:  {result.total_return_pct:+.2f}%")
    print(f"  Win rate:      {result.win_rate_pct:.1f}%")
    print(f"  Total trades:  {result.total_trades}")
    print(f"  Max drawdown:  {result.max_drawdown_pct:.2f}%")
    print(f"  Profit factor: {result.profit_factor:.2f}")
    print()
    return result


a = run("A — EMA20 > EMA50 on 4h (current)", use_price_vs_ema50=False)
b = run("B — price > EMA50 on 4h (proposed)", use_price_vs_ema50=True)

print("─" * 50)
print("  COMPARISON  (B minus A)")
print("─" * 50)
print(f"  Sharpe:        {b.sharpe_ratio - a.sharpe_ratio:+.3f}")
print(f"  Total return:  {b.total_return_pct - a.total_return_pct:+.2f}%")
print(f"  Win rate:      {b.win_rate_pct - a.win_rate_pct:+.1f}%")
print(f"  Total trades:  {b.total_trades - a.total_trades:+d}  (more = catches more entries)")
print(f"  Max drawdown:  {b.max_drawdown_pct - a.max_drawdown_pct:+.2f}%")
print()
winner = "B (price > EMA50)" if b.sharpe_ratio > a.sharpe_ratio else "A (EMA20 > EMA50)"
print(f"  Winner by Sharpe: {winner}")

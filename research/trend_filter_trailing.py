"""
Hypothesis 13: does adding a TRAILING STOP to the hypothesis-12 trend filter help?

Motivation: the deployed filter locks in nothing. Its only exit is a close below
the 150d SMA, so a +12.7% open gain can be handed back in full if price retraces
to the line. A trailing stop is the obvious intuition. Intuition is not evidence.

Rules of engagement (same as #12, plus):
- Signal from close[t]; position applied to day t+1. NO look-ahead.
- Trailing stop is a STANDING ORDER: it triggers INTRADAY on the low, and fills
  at the stop level — not at the close. Modelling stops on closes only is the
  same error as modelling liquidation on closes (methodology note 8).
- Peak tracked from intraday HIGHs since entry.
- Fee 0.10% on every position change, including stop-outs.
- Two re-entry policies tested, because it changes everything:
    PERMISSIVE  — re-enter next day if close > SMA (stop barely bites)
    FRESH-CROSS — after a stop-out, price must close BELOW the SMA before a new
                  entry is allowed (standard; prevents instant re-entry)
- Grid over BOTH lookback and stop distance — a single lucky cell is not a result.
- Benchmarked against buy-and-hold AND against the plain (no-stop) filter.
- Year-by-year, because an edge that is one bear market is fragility.
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trend_filter import fetch_btc_daily, metrics, FEE


def run_trailing(df, lookback, stop_pct, policy="fresh"):
    """Long/flat SMA filter with an optional trailing stop.

    stop_pct=None disables the stop (reproduces hypothesis 12 exactly).
    policy: 'fresh' requires a close below the SMA after a stop-out before
            re-entry; 'permissive' allows immediate re-entry on the SMA rule.
    """
    close = df["close"].values
    high  = df["high"].values
    low   = df["low"].values
    sma   = df["close"].rolling(lookback).mean().values
    sig   = np.where(close > sma, 1.0, 0.0)
    sig[np.isnan(sma)] = 0.0

    n = len(close)
    pos       = np.zeros(n)
    strat_ret = np.zeros(n)
    peak      = np.nan        # running high since entry (PRIOR days only)
    in_pos    = False
    blocked   = False         # fresh-cross lock after a stop-out
    n_trades  = n_stopped = 0

    for t in range(1, n):
        # release the fresh-cross lock once price closes back below the SMA
        if blocked and sig[t - 1] == 0.0:
            blocked = False
        want = (sig[t - 1] == 1.0) and not blocked

        if not want:
            # Mirror the H12 convention EXACTLY: the decision is taken at the
            # close of t-1 and executed there, so day t has NO exposure. Taking
            # day t's return before exiting is a one-day look-ahead and shifted
            # CAGR by 0.5pp when I first wrote it.
            if in_pos:
                strat_ret[t] = -FEE
                in_pos, peak = False, np.nan
            continue

        pos[t] = 1.0
        entry_fee = 0.0
        if not in_pos:
            in_pos, peak = True, close[t - 1]   # peak starts at the entry price
            entry_fee = FEE
            n_trades += 1

        # Stop is checked against the peak from PRIOR days. Using today's high
        # would assume the stop trailed up intraday before price fell back.
        stop_lv = peak * (1 - stop_pct) if stop_pct else -np.inf
        if stop_pct and low[t] <= stop_lv:
            strat_ret[t] = stop_lv / close[t - 1] - 1 - entry_fee - FEE
            in_pos, peak = False, np.nan
            n_stopped += 1
            if policy == "fresh":
                blocked = True
            continue

        peak = max(peak, high[t])
        strat_ret[t] = close[t] / close[t - 1] - 1 - entry_fee

    start  = lookback
    equity = np.cumprod(1 + strat_ret)
    eq     = equity[start:] / equity[start]
    m = metrics(eq, strat_ret[start:], len(eq))
    m.update(lookback=lookback, stop_pct=stop_pct, policy=policy,
             n_trades=n_trades, n_stopped=n_stopped,
             time_in_mkt=float(pos[start:].mean()),
             equity=eq, dates=df["date"].values[start:])
    return m


def main():
    print("Fetching BTC/USDT daily...")
    df = fetch_btc_daily()
    print(f"{len(df)} candles: {df['date'].iloc[0].date()} -> {df['date'].iloc[-1].date()}\n")

    LB = 150
    base = run_trailing(df, LB, None)
    bh_close = df["close"].values[LB:]
    bh_eq  = bh_close / bh_close[0]
    bh_ret = np.concatenate([[0.0], bh_close[1:] / bh_close[:-1] - 1])
    bh = metrics(bh_eq, bh_ret, len(bh_eq))

    print(f"{'variant':<34}{'CAGR':>8}{'maxDD':>9}{'Calmar':>8}{'Sharpe':>8}{'trades':>8}{'stops':>7}{'inMkt':>7}")
    print("-" * 89)
    print(f"{'BUY & HOLD':<34}{bh['cagr']*100:>7.1f}%{bh['maxdd']*100:>8.1f}%{bh['calmar']:>8.2f}"
          f"{bh['sharpe']:>8.2f}{1:>8}{'-':>7}{'100%':>7}")
    print(f"{'H12 plain filter (no stop)':<34}{base['cagr']*100:>7.1f}%{base['maxdd']*100:>8.1f}%"
          f"{base['calmar']:>8.2f}{base['sharpe']:>8.2f}{base['n_trades']:>8}{'-':>7}"
          f"{base['time_in_mkt']*100:>6.0f}%")
    print()

    results = {}
    for policy in ("fresh", "permissive"):
        for sp in (0.05, 0.10, 0.15, 0.20, 0.25):
            m = run_trailing(df, LB, sp, policy)
            results[(policy, sp)] = m
            print(f"{'  trail ' + str(int(sp*100)) + '%  (' + policy + ')':<34}"
                  f"{m['cagr']*100:>7.1f}%{m['maxdd']*100:>8.1f}%{m['calmar']:>8.2f}"
                  f"{m['sharpe']:>8.2f}{m['n_trades']:>8}{m['n_stopped']:>7}"
                  f"{m['time_in_mkt']*100:>6.0f}%")
        print()

    # ---- robustness surface: does any cell beat plain on Calmar? ----
    print("CALMAR SURFACE (lookback x stop) — plain filter's Calmar in brackets")
    print(f"{'lookback':>9} {'noStop':>8}" + "".join(f"{int(s*100):>7}%" for s in (0.05,0.10,0.15,0.20,0.25)))
    print("-" * 60)
    better = 0; total = 0
    for lb in (100, 125, 150, 175, 200):
        pl = run_trailing(df, lb, None)
        row = f"{lb:>9} {pl['calmar']:>8.2f}"
        for sp in (0.05, 0.10, 0.15, 0.20, 0.25):
            m = run_trailing(df, lb, sp, "fresh")
            total += 1
            if m["calmar"] > pl["calmar"]: better += 1
            row += f"{m['calmar']:>8.2f}"
        print(row)
    print(f"\ncells beating the no-stop filter on Calmar: {better}/{total}")

    # ---- year by year for the best stop variant ----
    best = max(results.values(), key=lambda m: m["calmar"])
    print(f"\nBEST STOP VARIANT: {int(best['stop_pct']*100)}% ({best['policy']}) "
          f"Calmar {best['calmar']:.2f} vs plain {base['calmar']:.2f}")
    d = pd.DataFrame({"date": pd.to_datetime(best["dates"]),
                      "stop_eq": best["equity"], "plain_eq": base["equity"]})
    d["yr"] = d["date"].dt.year
    print(f"\n{'year':>6}{'trail':>10}{'plain':>10}{'B&H':>10}")
    bhs = pd.Series(bh_eq, index=pd.to_datetime(base["dates"]))
    for yr, g in d.groupby("yr"):
        s = g["stop_eq"].iloc[-1]/g["stop_eq"].iloc[0] - 1
        p = g["plain_eq"].iloc[-1]/g["plain_eq"].iloc[0] - 1
        b = bhs[bhs.index.year == yr]
        bb = b.iloc[-1]/b.iloc[0] - 1 if len(b) > 1 else float("nan")
        print(f"{yr:>6}{s*100:>9.1f}%{p*100:>9.1f}%{bb*100:>9.1f}%")


if __name__ == "__main__":
    main()

# Strategy Research Log

Ten hypotheses tested against real data with fee accounting, benchmarks, and
fragility checks. Three real effects found; none profitable at small account size.

The **methodology** section is the reusable part — those checks killed six results
that looked strong at first pass.

---

## Summary of findings

| # | Hypothesis | Verdict | Why |
|---|---|---|---|
| 1 | 4-agent indicator consensus | No edge | Public inputs; −6.89% over 599d, 37% win rate |
| 2 | Funding predicts price direction | Rejected | t=4.7 collapsed to t=0.65 on non-overlapping data |
| 3 | Time-series momentum (1/3/6/12m) | Rejected | All variants lost to buy-and-hold on return *and* Sharpe |
| 4 | Volatility targeting | No alpha | Sharpe 0.77 vs 0.79 B&H; relocates risk, doesn't add return |
| 5 | Delta-neutral funding (BTC) | **Real** | +10.9%/yr gross, −0.44% max DD — but compressed to ~1.9% by 2026 |
| 6 | Alt funding premium | Rejected | High yields exist only where no spot leg exists to hedge |
| 7 | Cross-sectional momentum | Rejected | Equal-weight universe beat every momentum variant |
| 8 | New-listing drift | **Real** | −5.06% 7d excess vs BTC, t=−2.52, consistent 5 years — needs shorting |
| 9 | Order flow / microstructure | Rejected | Fee arithmetic: needs 82.8% accuracy vs 52–55% state of the art |
| 10 | Token unlock drift | **Real** | −2.99% 7d median excess, t=−4.31, 62% win — but only 2–5% CAGR when traded |
| 11 | LLM vs keyword news sentiment | Rejected | r collapses 0.312 → 0.015 once look-ahead removed; news is priced |

**Conclusion:** real inefficiencies exist and are findable. Capturing them requires
shorting or capital. A $30 spot account has neither. The strongest effect (#10)
isn't worth trading even at scale once liquidation risk is modelled.

---

## Methodology — the reusable part

### 1. Benchmark against doing nothing
BTC buy-and-hold 2017–2026: **+1,373%, 35.0% CAGR, Sharpe 0.79, −83.2% max DD.**
"Made a profit" is not the bar. "Beat holding, after fees, with less pain" is.

Cross-sectional momentum looked excellent (+2,209%) until compared to an
equal-weight basket of the same coins (+2,302%). The signal added nothing.

### 2. Never use overlapping windows
Sampling 7-day forward returns every 8 hours means each window shares ~95% of its
data with its neighbours. This inflated funding t-stats **~5x**.

Collapse events into distinct episodes, or sample at the holding-period interval.

### 3. Check concentration
If the top 3 of N periods carry most of the return, it's fragility, not edge.
- Time-series momentum: top 3 = 46% of return → fragile
- Unlock drift: top 5 = 7% of return → robust

### 4. Assume survivorship bias until proven otherwise
Backtesting today's listed coins silently excludes everything that died.
Direction matters: it inflated alt momentum, but made the unlock short look
*conservative* (delisted tokens crashed hardest).

### 5. Verify executability before believing a yield
Alt perps paying 12–26%/yr turned out to be tokenised stocks and commodities with
**no spot leg on the same venue** — the hedge was impossible. The high yield *was*
the compensation for that friction.

> When you find a high yield, ask what it's compensating for before assuming
> it's an inefficiency.

### 6. Fee arithmetic sets your minimum holding period
```
mean absolute BTC move       1m: 3.0bp   5m: 7.6bp   15m: 10.7bp   1h: 27.1bp
round-trip cost      spot taker: 20bp    perp taker: 8bp   perp maker: 4bp
% of moves exceeding 20bp     1m: 0%     5m: 6%      15m: 12%      1h: 47%
```
At spot fees you need **multi-hour to daily holds, minimum**. This predicted the
1h-vs-4h result before the backtest confirmed it, and killed order flow outright.

> Estimate the move your idea captures. If it isn't several times your round-trip
> cost, stop there.

### 7. Excess return ≠ tradeable return
An event study showing "underperforms BTC by 3%" does **not** mean a naked short
earns 3%. A token that rises 8% while BTC rises 15% underperformed — and shorting
it loses 8%.

Relative effects need a **hedged pair** (short token + long BTC). The naked version
of #10 lost 84%; the hedged version restored the 62% win rate.

### 8. Event studies don't tell you if the account survives
The unlock event study showed +2.78% median per trade. The portfolio simulation —
with position sizing, concurrent positions, margin, and liquidation on **intraday
highs** — showed −99% at $30.

Shorts die on wicks, not closes. Modelling liquidation on closing prices produces
a much prettier, entirely false result.

### 9. Event windows must start AFTER the information is known
Sentiment scored per 3-day bucket, correlated against returns measured from the
bucket's **start**, gave LLM r=+0.312 (t=3.86). Measured from the bucket's **end**
— so every headline predates the return window — it gave **r=+0.015 (t=0.18)**.

The entire signal was headlines from days 2-3 being correlated against a window
containing days 2-3. Description masquerading as prediction.

The tell was there beforehand: sentiment correlated with TRAILING returns at
r=+0.427. A scorer that reads the recent past well will manufacture a spurious
forward correlation if the windows overlap by even one day.

> Ask of any event study: was every input observable before the measurement
> window opened? Controlling for prior returns does NOT fix within-window leakage.

### 10. Minimum position size is a real constraint
```
Binance min notional      $5
Equity                   $30    -> forced position = 16.7% of account
Safe sizing for a strategy that occasionally loses 100% of position: 1-2%
=> requires ~$250-500 equity
```
Confirmed empirically: $30 → −99.2%; $100+ → consistently +60% win rate.

---

## Bugs found in this codebase

| File | Bug | Impact |
|---|---|---|
| `backtest.py` | Paging loop broke on any short page | **Every backtest ran on 1,999 candles (83 days, ending Feb 2025) instead of the requested range.** Fixed → 14,400 candles |
| `ops/hmm_model.pkl` | 43 days stale | Classified a flat market as `bull` → demanded an EMA stack that couldn't form. `trend_up` was True **0 times in 1,312 ticks** |
| `ml_filter.py` | `float()` on a size-1 array, removed in NumPy 2.0 | `predict()` raised on **every call**; fails open, so it silently passed 100% of signals while appearing installed |
| `.github/workflows/vm-watchdog.yml` | `curl -sf` treats HTTP 401 as failure | Dashboard is password-protected → healthy VM read as dead → **25 hourly VM resets** |
| `config.py` | `load_dotenv(override=True)` | `.env` beats shell env vars, so `VAR=x python bot.py` silently does nothing **locally** (works in CI, where no `.env` exists) |

---

## Data sources

| What | Where | Notes |
|---|---|---|
| OHLCV, order books | `ccxt` → Binance / KuCoin | Free. Binance spot history to 2017 |
| Funding rates | `binanceusdm.fetch_funding_rate_history` | Honours `since`, back to 2021. KuCoin ignores `since` (~1 month only) |
| Token unlocks | `defillama-datasets.llama.fi/emissions/<slug>` | **Free.** The documented `api.llama.fi/emissions` is paywalled (402); the datasets CDN is not |
| Protocol list | `defillama-datasets.llama.fi/emissionsProtocolsList` | 359 protocols |

Unlock records live in `metadata.events` with `unlockType == "cliff"`. Compute size
as `tokens / (circulating + tokens)` — dividing by a near-zero genesis supply
produces nonsense (observed: 288,000%).

---

## What would change these conclusions

- **Capital ≥ $250–500** — makes #10 survivable, though still only 2–5% CAGR
- **Capital ≥ $5,000** — makes #5 (delta-neutral funding) executable, *if* funding
  normalises from its compressed 2026 levels
- **Funding rates normalising** — #5 paid 30% in 2021 vs ~1.9% in 2026
- **Untested categories** — market making, cross-exchange arbitrage, statistical
  arbitrage, LLM-based context judgment (only forward-testable; historical tests
  are contaminated by hindsight)

---

*Eleven hypotheses. Three real effects. Zero convertible into money at $30.*
*Total cost of finding out: $0.07 in paper trading losses.*

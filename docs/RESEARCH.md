# Strategy Research Log

Thirteen hypotheses tested against real data with fee accounting, benchmarks, and
fragility checks. Four real effects found; three need shorting or more capital, but
the fourth — a long/flat 150-day BTC trend filter — is executable at $30 and is now
**deployed live in paper mode** (hypothesis 12, Aug 2026).

The **methodology** section is the reusable part — those checks killed seven results
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
| 12 | Long/flat 150d trend filter (BTC) | **Real & deployed** | CAGR ~35% ≈ B&H, maxDD ~−46% vs ~−80%; survives rolling walk-forward + whole-grid OOS. Insurance, not alpha |
| 13 | Trailing stop added to #12 | Rejected | Only the near-inert 25% stop beat plain on Calmar, and that gain is one year: remove 2019 and it flips to −29.6 pp. Active stops are destructive — a 5% trail cuts time-in-market from 51% to 6% |

**Conclusion:** real inefficiencies exist and are findable. Effects #5/#8/#10 require
shorting or capital a $30 spot account lacks. But #12 breaks the deadlock: judged on
*drawdown* rather than Sharpe (the account's true mandate is capital preservation), a
long/flat trend filter roughly halves buy-and-hold's max drawdown while matching its
full-cycle return — and, being long/flat spot with all-in/all-out sizing, needs neither
shorting nor a minimum-order workaround. It is the first effect converted into a live
(paper) strategy. It is crash insurance, not bull-market alpha — expect it to lag a
sustained rally. Details below.

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

### 10. An improvement that lives in one year is not an improvement
Adding a trailing stop to #12 looked like a win at first pass: the 25% variant
raised Calmar 0.79 -> 0.88 and cut maxDD 46.2% -> 42.2%.

Year-by-year, the stop changed anything in only 3 of 9 years:
```
2019  +48.3 pp     2021  -41.1 pp     2018  +11.5 pp
net   +18.6 pp     without 2019 alone:  -29.6 pp
```
The whole result was 2019. It also fired just 5 times in 9 years — the "best"
setting was the one closest to doing nothing, which is itself a warning sign.

Tighter stops were unambiguously destructive: a 5% trail cut CAGR from 36.3% to
8.4% and time-in-market from 51% to 6%. BTC retraces 20-30% *inside* uptrends,
so an active stop fires on ordinary volatility and then locks you out of the
recovery.

> When the best parameter in a sweep is the one that barely acts, you have
> measured the cost of acting, not the value of the feature.

### 11. Minimum position size is a real constraint
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
| scripts outside repo root | `load_dotenv()` resolves relative to the CALLING FILE | A scratchpad script got `KEY=None`, and Google reports that as "API key not valid". Pass an explicit path |
| `config.py` | `load_dotenv(override=True)` | `.env` beats shell env vars, so `VAR=x python bot.py` silently does nothing **locally** (works in CI, where no `.env` exists) |

---

## Data sources

| What | Where | Notes |
|---|---|---|
| OHLCV, order books | `ccxt` → Binance / KuCoin | Free. Binance spot history to 2017 |
| Funding rates | `binanceusdm.fetch_funding_rate_history` | Honours `since`, back to 2021. KuCoin ignores `since` (~1 month only) |
| Token unlocks | `defillama-datasets.llama.fi/emissions/<slug>` | **Free.** The documented `api.llama.fi/emissions` is paywalled (402); the datasets CDN is not |
| Protocol list | `defillama-datasets.llama.fi/emissionsProtocolsList` | 359 protocols |
| Historical headlines | GDELT `api.gdeltproject.org/api/v2/doc/doc` | Free, back to 2017. Filter `domain:` to match live feeds. Throttles hard — pace slowly, checkpoint every window |
| LLM scoring | `gemini-3.1-flash-lite` via Generative Language API | Jan 2025 cutoff (verified: knows Dec 2024, not Mar 2025+). Grounding OFF or the window is contaminated |

Unlock records live in `metadata.events` with `unlockType == "cliff"`. Compute size
as `tokens / (circulating + tokens)` — dividing by a near-zero genesis supply
produces nonsense (observed: 288,000%).

---

## Hypothesis 12 — long/flat trend filter (the one that shipped)

**Rule:** once per closed daily candle, hold BTC if close > 150-day SMA, else hold cash.
Long/flat only, spot, all-in/all-out. Fee 0.10% per position change (~5–15 flips/yr).

**Why it clears the walls the others hit:** no shorting (rule 7), no minimum-order sizing
trap (rule 10 — you're 100% in or 100% out, never fractionally sized), no liquidation risk
(rule 8 doesn't apply to unlevered spot — the drawdown numbers are real, not pre-liquidation
illusions). Fees are trivial at daily cadence (rule 6).

**Why it isn't a re-run of #3 (TSMOM, rejected):** #3 was judged on return and Sharpe and
lost. #12 is judged on **max drawdown / Calmar** — the correct objective for an account whose
mandate is capital preservation. Sharpe penalises upside vol equally; this account cares only
about the left tail.

**Evidence (Binance daily 2017–2026, fees on, no look-ahead — signal from close[t], applied
to return t→t+1):**
- Full sample, fixed L=150: CAGR 34.7%, Sharpe 0.88, **maxDD −46.2%**, Calmar 0.75
  vs B&H CAGR ~35%, Sharpe 0.64, **maxDD −77 to −83%**, Calmar 0.29.
- Rolling walk-forward 2019–2026 (lookback re-picked every 6mo on past data only): beats B&H
  on every metric.
- Whole-grid OOS 2022–2026: **6 of 7 lookbacks** beat B&H Calmar → parameter-robust, not luck.
- Year-by-year: edge recurs in 2018, 2022 *and* 2026 (multiple crashes) — not one event.

**Honest caveats:** it is insurance, not alpha — it trades away bull-market upside (lost to
B&H in 2020/2023/2024) for bear protection. Live drawdown expectation is **−45% to −60%**,
not the −31% seen in the 2022–2026 sub-window (don't cherry-pick). If BTC matures into a
low-vol grind, whipsaw cost stays while the crashes it feeds on shrink — forward testing,
not more backtesting, is what will reveal that.

**Deployment:** `STRATEGY=trend_filter` in `bot.py` (`_tick_trend_filter`). `EXCHANGE=kucoin`
on the VM (KuCoin serves ≥151 daily candles; agrees with Binance to the penny). Kill switch
raised 0.25→0.55 so a normal drawdown doesn't halt it. Fails loud on empty/stale(>48h)/NaN
data; long/flat state persists across restarts in `ops/trend_state.json`. Backtests in
`research/trend_filter*.py`. Live in paper since Aug 2026.

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

*Thirteen hypotheses. Four real effects. One convertible into money at $30 — now live.*
*Total cost of finding out: $0.07 in paper trading losses.*

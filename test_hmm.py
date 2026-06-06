"""
test_hmm.py — Standalone HMM regime detection validation script.

Fetches 730 days of BTC/USDT 1h data from Binance, trains the HMM,
plots regime detection on the full history, and prints distribution stats.

Usage:
    python test_hmm.py
    python test_hmm.py --days 365
    python test_hmm.py --load          # load existing model instead of retraining
"""

import argparse
import logging
import sys
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("test_hmm")


def main():
    parser = argparse.ArgumentParser(description="Test HMM regime detection")
    parser.add_argument("--days", type=int, default=730,
                        help="Days of historical data (default: 730)")
    parser.add_argument("--load", action="store_true",
                        help="Load existing model from ops/hmm_model.pkl instead of retraining")
    args = parser.parse_args()

    from hmm_engine import HMMRegimeDetector, REGIME_NAMES, REGIME_COLORS
    from backtest import WalkForwardBacktester

    hmm = HMMRegimeDetector()

    if args.load:
        print("Loading existing HMM model …")
        ok = hmm.load_model()
        if not ok:
            print("No saved model found — training a fresh one")
            args.load = False

    if not args.load:
        print(f"Fetching {args.days} days of BTC/USDT 1h data from Binance …")
        bt = WalkForwardBacktester()
        df = bt.fetch_historical(days=args.days, timeframe="1h")
        print(f"Fetched {len(df)} candles  ({df.index[0]} → {df.index[-1]})")

        print("\nTraining HMM …")
        ok = hmm.fit(df)
        if not ok:
            print("Training failed — see logs above")
            sys.exit(1)

        hmm.save_model()
        print("Model saved → ops/hmm_model.pkl")

        print("\nGenerating regime chart …")
        hmm.plot_regimes(df, save_path="ops/hmm_regimes.png")
        print("Chart saved → ops/hmm_regimes.png")
    else:
        # Still fetch data for inference and stats
        print(f"Fetching {args.days} days of BTC/USDT 1h data for inference …")
        bt = WalkForwardBacktester()
        df = bt.fetch_historical(days=args.days, timeframe="1h")
        print(f"Fetched {len(df)} candles")

        print("\nGenerating regime chart …")
        hmm.plot_regimes(df, save_path="ops/hmm_regimes.png")
        print("Chart saved → ops/hmm_regimes.png")

    # ── Run full-history prediction and print stats ────────────────────────────
    print("\nRunning full-history regime prediction …")
    features = hmm._extract_features(df)
    if features is None:
        print("Feature extraction failed — cannot compute stats")
        sys.exit(1)

    import numpy as np
    X      = hmm.scaler.transform(features)
    states = hmm.model.predict(X)
    regs   = [hmm._state_to_regime[s] for s in states]
    total  = len(regs)
    counts = Counter(regs)

    print("\n" + "─" * 50)
    print("  HMM REGIME DISTRIBUTION")
    print("─" * 50)
    for regime in REGIME_NAMES:
        n   = counts.get(regime, 0)
        pct = n / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {regime:<10}  {n:5d} bars  {pct:5.1f}%  {bar}")
    print(f"\n  Total bars: {total}  ({total/24:.0f} days)")

    # ── Transition matrix ──────────────────────────────────────────────────────
    print("\n  LEARNED TRANSITION PROBABILITIES")
    print("  (row = current state, col = next state)")
    header = "           " + "  ".join(f"{r[:6]:>6}" for r in REGIME_NAMES)
    print(header)
    for i in range(hmm.N_STATES):
        regime_name = hmm._state_to_regime[i]
        row = hmm.model.transmat_[i]
        # reorder row by regime name order
        ordered = [
            row[k]
            for k in range(hmm.N_STATES)
            if hmm._state_to_regime[k] == REGIME_NAMES[REGIME_NAMES.index(hmm._state_to_regime[k])]
        ]
        # actually just print in state-index order with regime labels
        row_str = "  ".join(f"{row[j]:6.3f}" for j in range(hmm.N_STATES))
        print(f"  {regime_name:<10}  {row_str}")

    # ── Current regime on most recent bars ────────────────────────────────────
    print("\n  MOST RECENT 10 BARS")
    recent_df = df.iloc[-len(features):].iloc[-10:]
    recent_features = features[-10:]
    recent_X = hmm.scaler.transform(recent_features)
    recent_posteriors = hmm.model.predict_proba(hmm.scaler.transform(features[-510:]))[-10:]
    recent_states = hmm.model.predict(hmm.scaler.transform(features[-510:]))[-10:]

    print(f"  {'Time':<20} {'Price':>10} {'Regime':<12} {'Confidence':>10}")
    for i, (ts, row) in enumerate(recent_df.iterrows()):
        state  = recent_states[i]
        regime = hmm._state_to_regime[state]
        conf   = recent_posteriors[i][state]
        print(f"  {str(ts)[:19]:<20} {row['close']:>10.2f} {regime:<12} {conf:>10.3f}")

    # ── Final prediction ───────────────────────────────────────────────────────
    regime, conf = hmm.predict_regime(df)
    print(f"\n  CURRENT REGIME: {regime.upper()}  (confidence={conf:.3f})")
    probs = hmm.get_regime_probabilities(df)
    print("  All probabilities:")
    for r in REGIME_NAMES:
        print(f"    {r:<10}: {probs.get(r, 0):.4f}")
    print("─" * 50 + "\n")

    print(f"Model age: {hmm.model_age_days():.1f} days")
    print(f"Needs retrain (30d threshold): {hmm.needs_retrain(30)}")


if __name__ == "__main__":
    main()

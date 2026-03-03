#!/usr/bin/env python3
"""Dump recent samples for selected features to CSV for inspection."""
import argparse
import os
import pandas as pd

from paper_trading.data_provider import create_data_provider


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--features', nargs='+', required=True)
    p.add_argument('--limit', type=int, default=200)
    p.add_argument('--out', default='backtest_results/psi_samples/feature_samples.csv')
    args = p.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=max(1000, args.limit))

    # take most recent rows
    sample = df.tail(args.limit)
    cols = ['timestamp'] + args.features
    missing = [c for c in cols if c not in sample.columns]
    if missing:
        print('Missing columns:', missing)
        # still write available columns
    sample[cols].to_csv(args.out, index=False)
    print('Wrote', args.out)


if __name__ == '__main__':
    main()

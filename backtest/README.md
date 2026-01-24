# Backtesting Framework

## Overview

Backtest engine for testing trading strategies against historical data.

## Features

- Historical data replay
- Realistic execution simulation
- Performance metrics calculation
- Regime-based analysis
- No look-ahead bias

## Usage
```python
from backtest.engine import BacktestEngine
from strategies.simple_trend import SimpleTrendStrategy

# Create strategy
strategy = SimpleTrendStrategy()

# Create backtest
engine = BacktestEngine(
    strategy=strategy,
    initial_capital=500,
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31)
)

# Run
result = engine.run()

# Analyze
print(f"Total Return: {result.total_return_pct:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2f}%")
```

## Key Classes

- `BacktestEngine`: Main execution engine
- `Trade`: Historical trade record
- `BacktestResult`: Complete results
- `PerformanceMetrics`: Metric calculations

## No Look-Ahead Bias

All decisions made using only data available at that time.
Features and regimes calculated chronologically.

## Realistic Execution

- Slippage: 0.1% (configurable)
- Fees: 0.075% (Binance actual)
- Stop loss checks on each candle
- Entry delays (1 candle)
import logging
from paper_trading import PaperTradingSystem
from strategies.orchestrator import MultiRegimeOrchestrator
from risk.engine import RiskEngine
from paper_trading.data_provider import create_data_provider
from paper_trading.execution import ExecutionSimulator
import json
import sys

logging.basicConfig(level=logging.INFO)

def main(limit=5000):
    model_dir = 'models/production/production_retrained_winsor_quantile_long'
    model_path = model_dir + '/model.pkl'

    system = PaperTradingSystem(
        initial_capital=500,
        symbol='BTC/USDT',
        timeframe='1h',
        speed='instant',
        data_source='historical'
    )

    strategy = MultiRegimeOrchestrator(use_ml=True, ml_model_path=model_path, ml_threshold=0.6)
    risk_engine = RiskEngine(capital=500)
    data_provider = create_data_provider('historical', symbol=system.symbol, timeframe=system.timeframe)
    execution_sim = ExecutionSimulator(base_slippage=0.001, base_fee_rate=0.00075, min_execution_delay=0.001, max_execution_delay=0.005)

    system.setup(strategy=strategy, risk_engine=risk_engine, data_provider=data_provider, execution_simulator=execution_sim)

    try:
        _ = data_provider.get_historical_data(limit=limit)
    except Exception:
        pass

    system.start()

    summary = system.get_performance_summary()
    out = 'backtest_results/production_smoke_extended.json'
    with open(out, 'w') as f:
        json.dump(summary, f, default=str, indent=2)
    print('Wrote', out)

if __name__ == '__main__':
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    main(limit=lim)

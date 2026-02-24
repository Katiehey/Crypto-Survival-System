import logging
from paper_trading import PaperTradingSystem
from strategies.orchestrator import MultiRegimeOrchestrator
from risk.engine import RiskEngine
from paper_trading.data_provider import create_data_provider
from paper_trading.execution import ExecutionSimulator
import json

logging.basicConfig(level=logging.INFO)

def main():
    model_path='models/production/production_20260215_fold0/model.pkl'

    system = PaperTradingSystem(
        initial_capital=500,
        symbol='BTC/USDT',
        timeframe='1h',
        speed='instant',
        data_source='historical'
    )

    strategy = MultiRegimeOrchestrator(use_ml=True, ml_model_path=model_path, ml_threshold=0.6)
    risk_engine = RiskEngine(capital=500)
    # Use the historical provider so feature pipeline runs (or DB-backed loader)
    data_provider = create_data_provider('historical', symbol=system.symbol, timeframe=system.timeframe)
    execution_sim = ExecutionSimulator(base_slippage=0.001, base_fee_rate=0.00075, min_execution_delay=0.001, max_execution_delay=0.005)

    system.setup(strategy=strategy, risk_engine=risk_engine, data_provider=data_provider, execution_simulator=execution_sim)
    
    # Historical provider will compute features if missing (no manual priming needed)
    # Attempt a warm-load to ensure pipeline runs and logs any issues early
    try:
        _ = data_provider.get_historical_data(limit=1000)
    except Exception:
        pass

    system.start()

    system.print_summary()
    execution_sim.print_statistics()

    summary = system.get_performance_summary()
    with open('backtest_results/production_smoke_summary.json','w') as f:
        json.dump(summary, f, default=str, indent=2)
    print('Wrote backtest_results/production_smoke_summary.json')

if __name__ == '__main__':
    main()

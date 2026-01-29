import pandas as pd
from backtest.engine import BacktestEngine
from strategies.simple_trend import SimpleTrendStrategy
from strategies.orchestrator import MultiRegimeOrchestrator

def run_final_comparison():
    print("🏁 Starting Final Comparison: Trend vs. Orchestrator")
    print("-" * 50)

    # 1. Run Original Strategy (The one that hit -7.9%)
    old_strategy = SimpleTrendStrategy()
    engine_old = BacktestEngine(strategy=old_strategy, initial_capital=500.0)
    res_old = engine_old.run()
    
    # 2. Run New Orchestrator (Using the green-zone parameters)
    new_strategy = MultiRegimeOrchestrator()
    engine_new = BacktestEngine(strategy=new_strategy, initial_capital=500.0)
    res_new = engine_new.run()

    # Summary Table
    print("\n" + "="*50)
    print("FINAL PERFORMANCE SUMMARY")
    print("="*50)
    print(f"{'Strategy':<25} | {'ROI %':<10}")
    print("-" * 50)
    print(f"{'Simple Trend':<25} | {res_old.total_return_pct:>9.2f}%")
    print(f"{'Smart Orchestrator':<25} | {res_new.total_return_pct:>9.2f}%")
    print("="*50)

if __name__ == "__main__":
    run_final_comparison()
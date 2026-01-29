import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from backtest.engine import BacktestEngine
from strategies.mean_reversion import MeanReversionStrategy # New Strategy

def run_sensitivity_analysis():
    # TESTING: Lookback windows (12h to 36h) vs. Band Tightness (1.5 to 3.0)
    windows = [12, 20, 24, 36]
    std_devs = [1.5, 2.0, 2.5, 3.0]
    
    results = []
    print("🚀 Starting Mean Reversion Sensitivity Test...")

    for win in windows:
        for std in std_devs:
            # Initialize the new Mean Reversion logic
            strategy = MeanReversionStrategy(
                window=win,
                std_dev=std
            )
            # Use R500 starting capital as we reset the DB earlier
            engine = BacktestEngine(strategy=strategy, initial_capital=500.0)
            result = engine.run() 
            
            results.append({
                'Window': win,
                'Std_Dev': std,
                'Return': result.total_return_pct
            })

    # Create Heatmap
    df = pd.DataFrame(results)
    pivot = df.pivot(index='Window', columns='Std_Dev', values='Return')
    
    plt.figure(figsize=(10, 6))
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="RdYlGn", center=0)
    plt.title("Mean Reversion ROI: Window Size vs Std Dev")
    plt.show()

if __name__ == "__main__":
    run_sensitivity_analysis()
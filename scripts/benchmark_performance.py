"""
Performance benchmarking script.

Measures system performance across various scenarios and dataset sizes.
"""

import time
import tracemalloc
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

from regime.features import (
    calculate_all_features,
    add_atr_features,
    add_efficiency_features,
    add_volume_features,
    calculate_complete_pipeline
)
from regime.classifier import RegimeClassifier


def create_synthetic_data(n_candles: int) -> pd.DataFrame:
    """
    Create synthetic OHLCV data for benchmarking.
    
    Args:
        n_candles: Number of candles to generate
        
    Returns:
        DataFrame with OHLCV data
    """
    np.random.seed(42)  # Reproducible
    
    prices = 42000 + np.cumsum(np.random.randn(n_candles) * 100)
    
    df = pd.DataFrame({
        'high': prices + np.random.uniform(50, 150, n_candles),
        'low': prices - np.random.uniform(50, 150, n_candles),
        'close': prices,
        'volume': 100 + np.abs(np.random.randn(n_candles) * 20)
    })
    
    return df


def benchmark_feature_calculation(n_candles: int, iterations: int = 3) -> Dict:
    """
    Benchmark feature calculation performance.
    
    Args:
        n_candles: Number of candles
        iterations: Number of iterations to average
        
    Returns:
        Dictionary with timing results
    """
    df = create_synthetic_data(n_candles)
    
    # Warm-up run
    _ = calculate_all_features(df.copy())
    
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        _ = calculate_all_features(df.copy())
        end = time.perf_counter()
        times.append(end - start)
    
    return {
        'n_candles': n_candles,
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'max_time': np.max(times),
    }


def benchmark_regime_classification(n_candles: int, iterations: int = 3) -> Dict:
    """
    Benchmark regime classification performance.
    
    Args:
        n_candles: Number of candles
        iterations: Number of iterations
        
    Returns:
        Dictionary with timing results
    """
    df = create_synthetic_data(n_candles)
    df = calculate_all_features(df)
    
    classifier = RegimeClassifier()
    
    # Warm-up
    _ = classifier.classify_dataframe(df.copy())
    
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        _ = classifier.classify_dataframe(df.copy())
        end = time.perf_counter()
        times.append(end - start)
    
    return {
        'n_candles': n_candles,
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'max_time': np.max(times),
    }


def benchmark_complete_pipeline(n_candles: int, iterations: int = 3) -> Dict:
    """
    Benchmark complete pipeline performance.
    
    Args:
        n_candles: Number of candles
        iterations: Number of iterations
        
    Returns:
        Dictionary with timing results
    """
    df = create_synthetic_data(n_candles)
    
    # Warm-up
    _ = calculate_complete_pipeline(df.copy())
    
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        _ = calculate_complete_pipeline(df.copy())
        end = time.perf_counter()
        times.append(end - start)
    
    return {
        'n_candles': n_candles,
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'max_time': np.max(times),
        'candles_per_second': n_candles / np.mean(times)
    }


def benchmark_individual_features(n_candles: int = 200) -> Dict:
    """
    Benchmark individual feature calculations.
    
    Args:
        n_candles: Number of candles
        
    Returns:
        Dictionary with individual feature timings
    """
    df = create_synthetic_data(n_candles)
    
    results = {}
    
    # ATR features
    start = time.perf_counter()
    _ = add_atr_features(df.copy())
    results['atr'] = time.perf_counter() - start
    
    # Efficiency features
    start = time.perf_counter()
    _ = add_efficiency_features(df.copy())
    results['efficiency'] = time.perf_counter() - start
    
    # Volume features
    start = time.perf_counter()
    _ = add_volume_features(df.copy())
    results['volume'] = time.perf_counter() - start
    
    return results


def measure_memory_usage(n_candles: int) -> Dict:
    """
    Measure memory usage during pipeline execution.
    
    Args:
        n_candles: Number of candles
        
    Returns:
        Dictionary with memory statistics
    """
    df = create_synthetic_data(n_candles)
    
    # Start memory tracking
    tracemalloc.start()
    
    # Run pipeline
    df_result = calculate_complete_pipeline(df)
    
    # Get memory stats
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Calculate DataFrame memory
    df_memory = df_result.memory_usage(deep=True).sum()
    
    return {
        'n_candles': n_candles,
        'current_mb': current / 1024 / 1024,
        'peak_mb': peak / 1024 / 1024,
        'dataframe_mb': df_memory / 1024 / 1024,
    }


def run_scalability_test() -> List[Dict]:
    """
    Test performance across different dataset sizes.
    
    Returns:
        List of benchmark results
    """
    sizes = [50, 100, 200, 500, 1000]
    results = []
    
    print("=" * 60)
    print("SCALABILITY TEST")
    print("=" * 60)
    print()
    
    for size in sizes:
        print(f"Testing {size} candles...")
        
        result = benchmark_complete_pipeline(size, iterations=3)
        result['size'] = size
        results.append(result)
        
        print(f"  Time: {result['mean_time']:.3f}s ± {result['std_time']:.3f}s")
        print(f"  Throughput: {result['candles_per_second']:.0f} candles/sec")
    
    return results


def main():
    """Run all performance benchmarks."""
    print("=" * 60)
    print("PERFORMANCE BENCHMARKING")
    print("=" * 60)
    print()
    
    # 1. Individual feature benchmarks
    print("1. Individual Feature Calculation Times (200 candles)")
    print("-" * 60)
    
    feature_times = benchmark_individual_features(200)
    
    for feature, time_sec in feature_times.items():
        print(f"  {feature:12s}: {time_sec*1000:6.2f} ms")
    
    print()
    
    # 2. Complete pipeline by size
    print("2. Complete Pipeline Performance")
    print("-" * 60)
    
    sizes = [50, 100, 200, 500]
    
    for size in sizes:
        result = benchmark_complete_pipeline(size, iterations=5)
        print(f"\n  {size} candles:")
        print(f"    Mean time: {result['mean_time']*1000:.2f} ms")
        print(f"    Std dev: {result['std_time']*1000:.2f} ms")
        print(f"    Throughput: {result['candles_per_second']:.0f} candles/sec")
    
    print()
    
    # 3. Feature vs Classification time
    print("3. Feature Calculation vs Regime Classification")
    print("-" * 60)
    
    n_test = 200
    
    feature_result = benchmark_feature_calculation(n_test, iterations=5)
    classify_result = benchmark_regime_classification(n_test, iterations=5)
    
    print(f"\n  Feature calculation: {feature_result['mean_time']*1000:.2f} ms")
    print(f"  Regime classification: {classify_result['mean_time']*1000:.2f} ms")
    
    total = feature_result['mean_time'] + classify_result['mean_time']
    feature_pct = (feature_result['mean_time'] / total) * 100
    classify_pct = (classify_result['mean_time'] / total) * 100
    
    print(f"\n  Feature calc: {feature_pct:.1f}% of total time")
    print(f"  Classification: {classify_pct:.1f}% of total time")
    
    print()
    
    # 4. Memory usage
    print("4. Memory Usage")
    print("-" * 60)
    
    for size in [100, 200, 500]:
        mem_stats = measure_memory_usage(size)
        print(f"\n  {size} candles:")
        print(f"    Peak memory: {mem_stats['peak_mb']:.2f} MB")
        print(f"    DataFrame size: {mem_stats['dataframe_mb']:.2f} MB")
    
    print()
    
    # 5. Scalability assessment
    print("5. Scalability Analysis")
    print("-" * 60)
    
    scalability_results = run_scalability_test()
    
    # Calculate scaling factor
    base_result = scalability_results[0]
    base_time_per_candle = base_result['mean_time'] / base_result['size']
    
    print(f"\n  Base time per candle: {base_time_per_candle*1000:.3f} ms")
    print(f"\n  Scaling efficiency:")
    
    for result in scalability_results[1:]:
        actual_time = result['mean_time']
        expected_linear_time = base_time_per_candle * result['size']
        efficiency = (expected_linear_time / actual_time) * 100
        
        print(f"    {result['size']:4d} candles: {efficiency:5.1f}% of linear")
    
    # Summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)
    
    # Target: 200 candles (typical use case)
    target_result = next(r for r in scalability_results if r['size'] == 200)
    
    print(f"\nTarget scenario (200 candles):")
    print(f"  Processing time: {target_result['mean_time']*1000:.2f} ms")
    print(f"  Throughput: {target_result['candles_per_second']:.0f} candles/sec")
    
    # Performance verdict
    target_time_ms = target_result['mean_time'] * 1000
    
    if target_time_ms < 500:
        verdict = "✅ EXCELLENT - Well within acceptable limits"
    elif target_time_ms < 1000:
        verdict = "✅ GOOD - Acceptable performance"
    elif target_time_ms < 2000:
        verdict = "⚠️  MODERATE - May need optimization"
    else:
        verdict = "❌ SLOW - Optimization required"
    
    print(f"\n  Performance verdict: {verdict}")
    
    # Bottleneck identification
    print(f"\n  Primary time consumer: Feature calculation ({feature_pct:.1f}%)")
    
    if feature_pct > 80:
        print("  Recommendation: Focus optimization on feature calculation")
    elif classify_pct > 50:
        print("  Recommendation: Focus optimization on regime classification")
    else:
        print("  Recommendation: No optimization needed")
    
    print("\n" + "=" * 60)
    print("✅ Benchmarking complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
"""Prototype robust sizing utilities (CVaR-based).

Provides a simple `cvar_position_size` function that estimates a conservative
position size based on historical returns and a target risk-per-trade budget.
This is a lightweight prototype for CVaR-style robust sizing.
"""
from typing import Sequence
import numpy as np


def cvar_position_size(returns: Sequence[float], capital: float = 1000.0, risk_per_trade_pct: float = 0.01, alpha: float = 0.95, min_size: float = 0.0, max_size: float = 1.0) -> float:
    """Estimate position size (fraction of capital) using CVaR (expected shortfall).

    Args:
        returns: Historical returns per-unit-position (negative numbers = losses).
        capital: Total capital available.
        risk_per_trade_pct: Fraction of capital willing to risk per trade (e.g., 0.01 = 1%).
        alpha: CVaR confidence level (e.g., 0.95).
        min_size, max_size: clamp the resulting size fraction.

    Returns:
        size_fraction: fraction of capital to risk (0..1)
    """
    if len(returns) == 0:
        return 0.0
    arr = np.asarray(returns, dtype=float)
    # We want the distribution of losses (negative returns). Take negative tail.
    # Compute VaR at alpha
    var = -np.percentile(arr, 100 * (1 - alpha))
    # CVaR (expected shortfall) approximation: mean of tail
    tail = arr[arr <= np.percentile(arr, 100 * (1 - alpha))]
    if tail.size == 0:
        cvar = var
    else:
        cvar = -np.mean(tail)

    # If cvar is zero (no historical losses), allow a small default
    if cvar <= 0:
        cvar = max(var, 1e-6)

    risk_budget = capital * float(risk_per_trade_pct)
    # size_fraction such that expected loss = size_fraction * cvar * capital ~= risk_budget
    size_fraction = risk_budget / (cvar * capital)
    size_fraction = float(np.clip(size_fraction, min_size, max_size))
    return size_fraction


def example():
    # Simple demonstration
    hist = [-0.01, -0.02, 0.005, -0.03, 0.01, -0.015, -0.005]
    size = cvar_position_size(hist, capital=1000.0, risk_per_trade_pct=0.01, alpha=0.95)
    print(f"Suggested size fraction: {size:.4f}")


if __name__ == '__main__':
    example()

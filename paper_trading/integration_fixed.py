"""
DEPRECATED: `integration_fixed.py` has been replaced by `integration.py`.

Please use `paper_trading.integration.create_integrated_paper_trading_system()`
or the `PaperTradingIntegrator` class in `paper_trading/integration.py`.

This file remains as a shim to avoid breaking older imports.
"""

from .integration import create_integrated_paper_trading_system as create_integrated_paper_trading_system  # re-export

__all__ = [
    'create_integrated_paper_trading_system'
]
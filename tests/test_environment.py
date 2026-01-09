"""
Environment setup validation tests
Ensures all dependencies are correctly installed
"""

import sys
import pytest


def test_python_version():
    """Verify Python version is 3.10 or higher"""
    assert sys.version_info >= (3, 10), "Python 3.10+ required"


def test_ccxt_import():
    """Test CCXT library imports correctly"""
    try:
        import ccxt
        assert hasattr(ccxt, 'binance')
    except ImportError:
        pytest.fail("CCXT not installed correctly")


def test_pandas_import():
    """Test pandas imports correctly"""
    try:
        import pandas as pd
        assert hasattr(pd, 'DataFrame')
    except ImportError:
        pytest.fail("Pandas not installed correctly")


def test_numpy_import():
    """Test numpy imports correctly"""
    try:
        import numpy as np
        assert hasattr(np, 'array')
    except ImportError:
        pytest.fail("Numpy not installed correctly")


def test_dotenv_import():
    """Test python-dotenv imports correctly"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        pytest.fail("python-dotenv not installed correctly")


def test_env_example_exists():
    """Verify .env.example file exists"""
    import os
    assert os.path.exists('.env.example'), ".env.example missing"


if __name__ == "__main__":
    pytest.main([__file__, '-v'])

#.venv/bin/python -m pytest tests/test_environment.py -v
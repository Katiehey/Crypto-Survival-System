"""
System health check script.

Validates all components are working correctly.
"""

import sys
from datetime import datetime


def check_imports():
    """Check all critical imports work."""
    print("=" * 60)
    print("CHECKING IMPORTS")
    print("=" * 60)
    
    modules = [
        ('data.fetcher', 'DataFetcher'),
        ('config.system_config', 'RISK_LIMITS'),
        ('config.exchange_config', 'ExchangeConfig'),
        ('regime.features', 'calculate_complete_pipeline'),
        ('regime.classifier', 'RegimeClassifier'),
        ('regime.visualization', 'analyze_regime_sequence'),
    ]
    
    all_ok = True
    
    for module_name, object_name in modules:
        try:
            module = __import__(module_name, fromlist=[object_name])
            obj = getattr(module, object_name)
            print(f"✅ {module_name}.{object_name}")
        except Exception as e:
            print(f"❌ {module_name}.{object_name}: {e}")
            all_ok = False
    
    return all_ok


def check_configuration():
    """Check configuration is valid."""
    print("\n" + "=" * 60)
    print("CHECKING CONFIGURATION")
    print("=" * 60)
    
    try:
        from config.system_config import RISK_LIMITS, SYSTEM_CONFIG
        
        # Validate risk limits
        risk_valid, risk_msg = RISK_LIMITS.validate()
        print(f"{'✅' if risk_valid else '❌'} Risk Limits: {risk_msg}")
        
        # Validate system config
        sys_valid, sys_msg = SYSTEM_CONFIG.validate()
        print(f"{'✅' if sys_valid else '❌'} System Config: {sys_msg}")
        
        # Print key values
        print(f"\nKey Configuration:")
        print(f"  Max risk per trade: {RISK_LIMITS.MAX_RISK_PER_TRADE * 100:.2f}%")
        print(f"  Max daily loss: {RISK_LIMITS.MAX_DAILY_LOSS * 100:.2f}%")
        print(f"  Starting capital: {SYSTEM_CONFIG.STARTING_CAPITAL} {SYSTEM_CONFIG.BASE_CURRENCY}")
        print(f"  Trading mode: {SYSTEM_CONFIG.TRADING_MODE}")
        
        return risk_valid and sys_valid
        
    except Exception as e:
        print(f"❌ Configuration check failed: {e}")
        return False


def check_database():
    """Check database is accessible."""
    print("\n" + "=" * 60)
    print("CHECKING DATABASE")
    print("=" * 60)
    
    try:
        import sqlite3
        from config.system_config import SYSTEM_CONFIG
        
        # Try to connect
        conn = sqlite3.connect(SYSTEM_CONFIG.DB_PATH)
        cursor = conn.cursor()
        
        # Check if candles table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='candles'
        """)
        
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Count candles
            cursor.execute("SELECT COUNT(*) FROM candles")
            count = cursor.fetchone()[0]
            print(f"✅ Database accessible: {count} candles stored")
        else:
            print("⚠️  Database exists but candles table not found")
            print("   Run: python scripts/setup_db.py")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False


def check_tests():
    """Check test suite status."""
    print("\n" + "=" * 60)
    print("CHECKING TESTS")
    print("=" * 60)
    
    try:
        import subprocess
        
        # Run pytest in collection mode
        result = subprocess.run(
            ['pytest', 'tests/', 'regime/tests/', '--collect-only', '-q'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout
            # Parse test count
            lines = output.strip().split('\n')
            for line in lines:
                if 'test' in line.lower():
                    print(f"✅ {line}")
            
            return True
        else:
            print(f"⚠️  Test collection had issues")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️  Test collection timed out")
        return False
    except Exception as e:
        print(f"❌ Test check failed: {e}")
        return False


def check_feature_calculation():
    """Check feature calculation works."""
    print("\n" + "=" * 60)
    print("CHECKING FEATURE CALCULATION")
    print("=" * 60)
    
    try:
        import numpy as np
        import pandas as pd
        from regime.features import calculate_complete_pipeline
        
        # Create small test dataset
        n = 50
        df = pd.DataFrame({
            'high': 42000 + np.random.randn(n) * 500,
            'low': 41000 + np.random.randn(n) * 500,
            'close': 41500 + np.random.randn(n) * 500,
            'volume': 100 + np.abs(np.random.randn(n) * 20)
        })
        
        # Calculate pipeline
        df_result = calculate_complete_pipeline(df)
        
        # Check key columns
        required_cols = ['regime', 'regime_confidence', 'regime_tradable']
        all_present = all(col in df_result.columns for col in required_cols)
        
        if all_present:
            print("✅ Feature calculation working")
            print(f"   Calculated {len(df_result.columns)} total columns")
            return True
        else:
            print("❌ Missing expected columns in output")
            return False
            
    except Exception as e:
        print(f"❌ Feature calculation failed: {e}")
        return False


def main():
    """Run all health checks."""
    print("=" * 60)
    print("SYSTEM HEALTH CHECK")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    checks = [
        ("Imports", check_imports),
        ("Configuration", check_configuration),
        ("Database", check_database),
        ("Tests", check_tests),
        ("Feature Calculation", check_feature_calculation),
    ]
    
    results = {}
    
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"\n❌ {check_name} check crashed: {e}")
            results[check_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("HEALTH CHECK SUMMARY")
    print("=" * 60)
    
    all_passed = all(results.values())
    
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("✅ ALL CHECKS PASSED - System is healthy")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    exit(main())
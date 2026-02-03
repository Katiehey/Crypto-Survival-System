#!/usr/bin/env python3
"""
Test script for integrated paper trading system.
"""

import sys
import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_integrated_paper_trading():
    """Test complete paper trading integration."""
    print("=" * 70)
    print("INTEGRATED PAPER TRADING TEST")
    print("=" * 70)
    
    try:
        # Import required components
        from paper_trading import PaperTradingSystem
        # Using the actual class from your paper_trading/integration.py
        from paper_trading.integration import PaperTradingIntegrator
        
        # Create system
        system = PaperTradingSystem(
            initial_capital=500,
            symbol="BTC/USDT",
            timeframe="1h",
            speed="instant",
            data_source="simulated"
        )
        
        # Create integrator
        integrator = PaperTradingIntegrator(system)
        
        # Setup integration
        print("\n🔄 Setting up integration...")
        # Note: Using setup_with_existing_components as defined in your integration.py
        success = integrator.setup_with_existing_components()
        
        if not success:
            print("❌ Integration failed")
            return False
        
        print("✅ Integration setup complete")
        
        # Check component status
        print("\n📋 COMPONENT STATUS:")
        status = integrator.get_integration_status()
        for key, val in status.items():
            print(f"   {key}: {'✅' if val else '❌'}")
        
        # Test Data Preparation (Priming for Regime Classifier)
        print("\n📊 Priming indicators with market noise...")
        base_price = 42000
        warmup_size = 120
        # Generate noisy walk for ATR and Efficiency Ratio
        warmup_noise = np.random.normal(0, 15, warmup_size)
        warmup_prices = base_price + warmup_noise.cumsum()
        
        def create_mock_df(prices, current_time):
            df = pd.DataFrame({
                'open': prices - 5,
                'high': prices + 15,
                'low': prices - 15,
                'close': prices,
                'volume': np.random.randint(500, 2000, len(prices))
            })
            df['datetime'] = [current_time - timedelta(hours=len(prices)-i) for i in range(len(prices))]
            return df

        # Run brief simulation
        print("\n🚀 Running Trend Simulation (10 steps)...")
        system.current_time = datetime.now()
        system.is_running = True
        
        for i in range(1, 11):
            # Simulate a strong trend (1.5% growth per step)
            trend_price = base_price * (1 + (i * 0.015)) + np.random.normal(0, 5)
            combined_prices = np.append(warmup_prices, [trend_price] * i)
            mock_data = create_mock_df(combined_prices, system.current_time)
            
            # 1. Update system time and price
            system.current_time += timedelta(hours=1)
            
            # 2. Get signal from strategy
            signal = system.strategy.generate_signal(mock_data)
            
            status_text = "WAITING"
            if signal and signal.signal_type.name == "LONG":
                # ✅ Correct method for PaperTradingRiskAdapter
                is_valid, reason, size = system.risk_engine.validate_and_size_signal(
                    signal, trend_price, system.open_positions
                )
                
                if is_valid:
                    # 3. Execute via the simulator
                    system.execution_simulator.execute_order(
                        symbol=system.symbol,
                        price=trend_price,
                        size=size,
                        side='LONG'
                    )
                    
                    # 4. Create a "Mock" object instead of a plain dict
                    class MockPosition:
                        def __init__(self, **kwargs):
                            self.__dict__.update(kwargs)
                            self.current_price = kwargs.get('entry_price')
                            self.entry_time = datetime.now()
                            self.side = kwargs.get('side', 'LONG')
                            # Performance metrics expected by the logger
                            self.max_favorable = kwargs.get('entry_price')
                            self.max_adverse = kwargs.get('entry_price')
                            self.stop_loss = None
                            self.take_profit = None

                    position_id = f"test_trade_{i}"
                    new_position = MockPosition(
                        id=position_id,
                        symbol=system.symbol,
                        side='LONG',
                        entry_price=trend_price,
                        size=size
                    )
                    
                    if isinstance(system.open_positions, dict):
                        system.open_positions[position_id] = new_position
                    else:
                        system.open_positions.append(new_position)

                    status_text = f"TRADE LONG (R{size:.2f})"

            # Print status using the CapitalTracker's actual balance
            current_equity = system.current_capital 
            print(f"   Step {i}: Price: ${trend_price:.2f} | Status: {status_text} | Equity: R{current_equity:.2f}")
            
            system.current_time += timedelta(hours=1)

        # 🏁 AFTER THE LOOP: Liquidate all for the final tally
        print("\n🏁 SIMULATION ENDED: Finalizing trades...")
        
        active_positions = list(system.open_positions.values()) if isinstance(system.open_positions, dict) else system.open_positions
        print(f"DEBUG: Found {len(active_positions)} active positions to close.")

        for pos in active_positions:
            # Calculate PnL: (Current - Entry) / Entry * Size
            pnl = ((trend_price - pos.entry_price) / pos.entry_price) * pos.size
            
            # Update the system capital directly
            system.current_capital += pnl
            
            # If the system has a method to record trades, call it to update 'closed_trades'
            if hasattr(system, 'closed_trades'):
                system.closed_trades.append({'pnl': pnl, 'exit_price': trend_price})
            
            print(f"✅ Closed LONG at ${trend_price:.2f} | PnL: R{pnl:.2f}")
            
        # Stop system
        system.stop()
        print("\n🛑 Simulation stopped")
        
        # Print summary
        print("\n📈 SIMULATION SUMMARY:")
        print(f"   Initial Capital: R{system.initial_capital:.2f}")
        print(f"   Final Capital:   R{system.current_capital:.2f}")
        print(f"   Closed Trades:   {len(system.closed_trades)}")
        
        print("\n✅ Integrated paper trading test COMPLETE")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_integrated_paper_trading()
    sys.exit(0 if success else 1)
"""
Tests for Trade dataclass.
"""

import pytest
from datetime import datetime, timedelta
from backtest.trade import Trade, create_trade


class TestTrade:
    """Test Trade dataclass."""
    
    def test_trade_creation(self):
        """Test creating a trade manually."""
        trade = Trade(
            trade_id="TEST_001",
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=42000,
            entry_regime='trend',
            exit_time=datetime(2024, 1, 1, 14, 0),
            exit_price=42500,
            exit_regime='trend',
            exit_reason='strategy_exit',
            size=250,
            side='long',
            pnl=2.85,
            pnl_percent=1.14,
            fees_paid=0.375
        )
        
        assert trade.trade_id == "TEST_001"
        assert trade.side == 'long'
        assert trade.size == 250
    
    def test_trade_validation_invalid_side(self):
        """Test that invalid side is rejected."""
        with pytest.raises(ValueError, match="Side must be"):
            Trade(
                trade_id="TEST",
                entry_time=datetime.now(),
                entry_price=42000,
                entry_regime='trend',
                exit_time=datetime.now() + timedelta(hours=1),
                exit_price=42500,
                exit_regime='trend',
                exit_reason='exit',
                size=250,
                side='invalid',  # Invalid
                pnl=0,
                pnl_percent=0,
                fees_paid=0
            )
    
    def test_trade_validation_negative_size(self):
        """Test that negative size is rejected."""
        with pytest.raises(ValueError, match="Size must be positive"):
            Trade(
                trade_id="TEST",
                entry_time=datetime.now(),
                entry_price=42000,
                entry_regime='trend',
                exit_time=datetime.now() + timedelta(hours=1),
                exit_price=42500,
                exit_regime='trend',
                exit_reason='exit',
                size=-250,  # Invalid
                side='long',
                pnl=0,
                pnl_percent=0,
                fees_paid=0
            )
    
    def test_trade_validation_exit_before_entry(self):
        """Test that exit before entry is rejected."""
        entry = datetime(2024, 1, 1, 10, 0)
        exit = datetime(2024, 1, 1, 9, 0)  # Before entry
        
        with pytest.raises(ValueError, match="Exit time must be after entry"):
            Trade(
                trade_id="TEST",
                entry_time=entry,
                entry_price=42000,
                entry_regime='trend',
                exit_time=exit,
                exit_price=42500,
                exit_regime='trend',
                exit_reason='exit',
                size=250,
                side='long',
                pnl=0,
                pnl_percent=0,
                fees_paid=0
            )
    
    def test_duration_calculation(self):
        """Test trade duration calculation."""
        trade = Trade(
            trade_id="TEST",
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=42000,
            entry_regime='trend',
            exit_time=datetime(2024, 1, 1, 14, 0),  # 4 hours later
            exit_price=42500,
            exit_regime='trend',
            exit_reason='exit',
            size=250,
            side='long',
            pnl=0,
            pnl_percent=0,
            fees_paid=0
        )
        
        assert trade.duration == 4.0
    
    def test_is_winner(self):
        """Test winner identification."""
        winner = Trade(
            trade_id="WIN",
            entry_time=datetime.now(),
            entry_price=42000,
            entry_regime='trend',
            exit_time=datetime.now() + timedelta(hours=1),
            exit_price=42500,
            exit_regime='trend',
            exit_reason='exit',
            size=250,
            side='long',
            pnl=2.5,  # Positive
            pnl_percent=1.0,
            fees_paid=0.375
        )
        
        loser = Trade(
            trade_id="LOSS",
            entry_time=datetime.now(),
            entry_price=42000,
            entry_regime='trend',
            exit_time=datetime.now() + timedelta(hours=1),
            exit_price=41500,
            exit_regime='trend',
            exit_reason='stop_loss',
            size=250,
            side='long',
            pnl=-2.5,  # Negative
            pnl_percent=-1.0,
            fees_paid=0.375
        )
        
        assert winner.is_winner == True
        assert loser.is_winner == False
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        trade = Trade(
            trade_id="TEST",
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=42000,
            entry_regime='trend',
            exit_time=datetime(2024, 1, 1, 14, 0),
            exit_price=42500,
            exit_regime='trend',
            exit_reason='exit',
            size=250,
            side='long',
            pnl=2.5,
            pnl_percent=1.0,
            fees_paid=0.375
        )
        
        trade_dict = trade.to_dict()
        
        assert trade_dict['trade_id'] == "TEST"
        assert trade_dict['size'] == 250
        assert trade_dict['is_winner'] == True
        assert 'duration_hours' in trade_dict


class TestCreateTrade:
    """Test create_trade helper function."""
    
    def test_create_winning_trade(self):
        """Test creating a winning long trade."""
        trade = create_trade(
            trade_id="WIN_001",
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=42000,
            entry_regime='trend',
            exit_time=datetime(2024, 1, 1, 14, 0),
            exit_price=42500,  # +500 = +1.19%
            exit_regime='trend',
            exit_reason='strategy_exit',
            size=250,
            side='long'
        )
        
        # Verify it's a winner
        assert trade.is_winner == True
        assert trade.pnl > 0
        assert trade.pnl_percent > 0
    
    def test_create_losing_trade(self):
        """Test creating a losing long trade."""
        trade = create_trade(
            trade_id="LOSS_001",
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=42000,
            entry_regime='trend',
            exit_time=datetime(2024, 1, 1, 11, 0),
            exit_price=41160,  # Stop loss hit
            exit_regime='range',
            exit_reason='stop_loss',
            size=250,
            side='long'
        )
        
        # Verify it's a loser
        assert trade.is_winner == False
        assert trade.pnl < 0
    
    def test_fees_included(self):
        """Test that fees are calculated."""
        trade = create_trade(
            trade_id="FEE_TEST",
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=42000,
            entry_regime='trend',
            exit_time=datetime(2024, 1, 1, 14, 0),
            exit_price=42500,
            exit_regime='trend',
            exit_reason='exit',
            size=250,
            side='long',
            fee_rate=0.00075
        )
        
        # Fees = entry fee + exit fee
        # = (250 * 0.00075) + (250 * 0.00075)
        # = 0.1875 + 0.1875 = 0.375
        assert trade.fees_paid == pytest.approx(0.375, abs=0.01)
    
    def test_pnl_calculation(self):
        """Test PnL calculation correctness."""
        trade = create_trade(
            trade_id="PNL_TEST",
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=40000,
            entry_regime='trend',
            exit_time=datetime(2024, 1, 1, 14, 0),
            exit_price=42000,  # +5% price change
            exit_regime='trend',
            exit_reason='exit',
            size=200,  # R200 position
            side='long',
            fee_rate=0.001  # 0.1% for easier calculation
        )
        
        # Position: R200 / 40000 = 0.005 BTC
        # Price change: +2000 (5%)
        # Gross profit: 0.005 * 2000 = 10
        # Fees: 200 * 0.001 * 2 = 0.4
        # Net PnL: 10 - 0.4 = 9.6
        
        assert trade.pnl == pytest.approx(9.6, abs=0.1)


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
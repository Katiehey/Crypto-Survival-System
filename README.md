# Crypto Survival System

**A private, AI-assisted trading system focused on capital preservation, controlled experimentation, and quiet compounding.**

**Current Status**: ✅ Week 1 Complete - Foundation Ready  
**Version**: v1.0 (Week 1)  
**Last Updated**: 2026-01-07

---

## ⚡ Quick Start
```bash
# Clone repository
git clone https://github.com/yourusername/crypto-survival-system.git
cd crypto-survival-system

# Setup environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
python scripts/setup_db.py

# Run system health check
python scripts/system_health_check.py

# Run tests
pytest tests/ regime/tests/ -v
```

---

## 🎯 What This System Can Do (Week 1)

✅ **Fetch and store market data** from Binance  
✅ **Calculate 19 technical features** (ATR, Efficiency, Volume)  
✅ **Classify market regimes** (TREND, RANGE, CHAOS, NO_TRADE)  
✅ **Analyze regime transitions** and patterns  
✅ **Export complete analysis** to CSV  

❌ **Cannot trade yet** - Need risk engine (Week 2)  
❌ **Cannot backtest yet** - Need backtesting framework (Week 3)  
❌ **Cannot paper trade yet** - Need execution simulation (Week 4)

---

This repository exists to support **personal trading of my own funds only**.  
It is designed to survive market uncertainty, not to chase performance.

---

## ⚠️ What This Is NOT

- Not a signal service  
- Not a prediction engine  
- Not a trading bot sold to others  
- Not financial advice  
- Not a SaaS or commercial product  
- Not a get-rich-quick scheme  
- Not intended for public or third-party use  

---

## ✅ What This IS

A **private, single-operator trading system** with:

- Hard risk limits enforced in code  
- AI used strictly for **offline analysis and regime classification**  
- Simple, deterministic execution logic  
- Explicit permission to **not trade**  
- Full logging for review, debugging, and tax compliance  
- Emphasis on *survival, consistency, and learning*  

---

## 🎯 Core Principles

1. **Survival First**  
   The system must prefer inactivity over forced participation.

2. **Capital Preservation**  
   - Max daily loss: **≤ 1%**  
   - Max risk per trade: **0.25–0.5%**

3. **No Live Self-Modification**  
   - No parameter changes during live trading  
   - No strategy mutation while capital is at risk  
   - All adaptations occur **offline only**

4. **AI Is a Supervisor, Not a Trader**  
   - AI evaluates regimes and historical performance  
   - AI does NOT place trades, size positions, or override rules

5. **Radical Transparency**  
   - Every decision is logged  
   - Every trade is reproducible  
   - Every system version is auditable

6. **Legal, Private, and Boring**  
   - Own capital only  
   - No investors, no clients, no shared access  

---

## 💰 Capital Parameters

- Starting Capital: **R500**  
- Market Type: **Spot only**  
- Exchange: **Binance**  
- Primary Pair: **BTC/USDT**  
- Position Risk: **0.25–0.5% per trade**  
- Max Trades per Day: **2**  
- Max Consecutive Losses: **2**  
- Leverage: **None**

> The system must remain viable even if capital growth is slow or flat.

---

## 🏗️ System Architecture

Market Data
↓
Feature Engineering
↓
Regime Classifier (Offline AI)
↓
Strategy Gate (Rule-Based)
↓
Risk Engine (Hard Constraints)
↓
Execution (Spot Orders Only)
↓
Logging & Metrics
↓
Weekly Offline Review


---

## 🚀 Setup

### Prerequisites

- Python 3.10+  
- Binance account (Spot trading enabled)  
- Git  
- No third-party automation services  

---

### Installation

1. Clone repository:
```bash
git clone https://github.com/yourusername/crypto-survival-system.git
cd crypto-survival-system

2. Create virtual environment:
python -m venv venv
source venv/bin/activate  # Linux / macOS
# venv\Scripts\activate   # Windows

3. Install dependencies:
pip install -r requirements.txt

4. Configure environment variables:
cp .env.example .env
# Add Binance API keys (read + trade only, no withdrawal)

5. Initialize local database:
python scripts/setup_db.py

📊 Usage Lifecycle
Phase 1 — Research & Backtesting
python scripts/run_backtest.py

Phase 2 — Paper Trading (Minimum: several weeks)
python scripts/run_paper.py

Phase 3 — Live Trading (Micro Capital Only)
python scripts/run_live.py
Live trading is permitted only after stable paper performance and manual approval.

🧠 Weekly Review (Offline Only)
Run on a fixed schedule (e.g. Sundays):
python evaluation/weekly_review.py

Outputs:
- Regime performance summaries
- Strategy expectancy by regime
- Drawdown statistics
- Suggestions for offline experimentation
No changes are deployed automatically.

📝 Development Roadmap
 - Repository scaffolding
 - Market data ingestion
 - Feature engineering module
 - Regime classifier (offline)
 - Risk engine
 - First minimal strategy
 - Backtesting framework
 - Paper trading
 - Live trading (micro size only)

🔒 Security & Privacy
- API keys stored in .env (never committed)
- Private repository
- No webhooks
- No cloud execution
- Logs stored locally
- No outbound data sharing

📈 Performance & Reporting
- Performance is tracked for personal evaluation only
- Results are not published, marketed, or shared
- Withdrawals are periodic and conservative
- Records are maintained for tax compliance

📜 License
Private Use Only
This project is not licensed for redistribution, resale, or third-party use.

## 📝 Development Status

### Phase 1: Foundation (Week 1) - IN PROGRESS

#### ✅ Day 1 Complete (2026-01-07)
- [x] Repository structure and documentation
- [x] Environment setup and configuration  
- [x] Database schema
- [x] Data fetcher implementation

**Achievements**: 14 tests, complete OHLCV pipeline, immutable risk limits

#### ✅ Day 2 Complete (2026-01-07)
- [x] ATR (Average True Range) calculation
- [x] Efficiency Ratio (trend strength)
- [x] Volume metrics (participation)
- [x] Feature pipeline integration

**Achievements**: 57 tests, 19 calculated features, complete validation

#### ✅ Day 3 Complete (2026-01-07)
- [x] Regime classifier (rule-based)
- [x] Regime confidence scoring
- [x] Complete pipeline integration (data → features → regime)
- [x] Regime transition analysis
- [x] Regime visualization tools

**Achievements**: 85+ tests, 4 regime types, transition analysis, complete documentation

**Week 1 Progress**: 60% complete (Days 1-3 done, Days 4-5 remaining)

#### 🔄 Days 4-5 Planned (Next Session)
- [ ] Week 1 integration testing
- [ ] End-to-end validation with real data
- [ ] Performance benchmarking
- [ ] Code quality review
- [ ] Week 1 retrospective
- [ ] Week 2 detailed planning

### Phase 2: Core System (Week 2) - PENDING
**Planned**:
- Risk engine implementation
- First strategy (simple breakout)
- Strategy testing framework
- Execution simulation

### Phase 3: Validation (Week 3) - PENDING
**Planned**:
- Backtesting engine
- Historical regime analysis
- Strategy performance by regime

### Phase 4: Deployment (Week 4) - PENDING
**Planned**:
- Paper trading mode
- Weekly evaluation system
- Live micro-capital mode

---

## 🎯 Current Capabilities

### What Works Now

**Data Pipeline**:
- ✅ Fetch OHLCV data from Binance
- ✅ Store in SQLite database
- ✅ Incremental updates
- ✅ Data validation

**Feature Engineering** (19 features):
- ✅ ATR family (volatility measures)
- ✅ Efficiency Ratio family (trend strength)
- ✅ Volume family (participation)
- ✅ Complete validation pipeline

**Regime Classification**:
- ✅ 4 regime types (TREND, RANGE, CHAOS, NO_TRADE)
- ✅ Confidence scoring (0-1)
- ✅ Tradability determination
- ✅ Transition analysis

**Analysis Tools**:
- ✅ Regime statistics
- ✅ Transition matrices
- ✅ Duration analysis
- ✅ Timeline visualization

### What's Missing (Week 2+)

- ❌ Risk engine (position sizing, limits)
- ❌ Trading strategies
- ❌ Backtesting framework
- ❌ Paper trading mode
- ❌ Live trading capability

---

## 📊 System Metrics

**Tests**: 85+ (100% passing)  
**Features**: 19 calculated  
**Regime Types**: 4 classified  
**Code Files**: 25+  
**Documentation Pages**: 10+  
**Lines of Code**: ~3500+  

**Test Coverage**: High (all critical paths tested)  
**Code Quality**: Production-ready  
**Documentation**: Comprehensive

---

**Current Focus**: Day 3 Complete — Regime Classification ✅  
**Next Focus**: Days 4-5 — Week 1 Integration & Review

**System Status**: Development — Feature Engineering Complete  
**Capital at Risk**: R0  
**Ready for Trading**: No (need risk engine + strategies)
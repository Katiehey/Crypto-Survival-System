# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Contributing guidelines with commit standards
- Architectural decision log (ADR)
- Maintenance procedures documentation
- Troubleshooting guide
- Updated README with development progress

### Added
- Data fetcher implementation using CCXT
- OHLCV candle storage in SQLite
- Rate limit handling and error recovery
- Data update script for manual refreshes
- Comprehensive data fetcher tests (8 tests)

### Added
- ATR (Average True Range) calculation
- True Range calculation with gap handling
- ATR percentile tracking over rolling window
- ATR normalization (percentage of price)
- Comprehensive ATR validation
- 13 ATR tests with known values (all passing)
- Real data validation script

### Added
- Efficiency Ratio (Kaufman) calculation
- Efficiency percentile tracking
- Efficiency smoothing for noise reduction
- Trend strength classification (strong/moderate/weak/none)
- 17 comprehensive efficiency tests (all passing)
- Combined feature validation script

### Added
- Volume moving average calculation
- Volume ratio (current vs average)
- Volume percentile tracking
- Volume regime classification (low/normal/high/very_high)
- Volume spike detection
- 18 comprehensive volume tests (all passing)
- Complete feature pipeline integration test

### Added
- Unified feature calculation pipeline (calculate_all_features)
- Complete feature validation function
- Feature summary statistics generator
- CSV export functionality for features
- Feature calculation script (scripts/calculate_features.py)
- 9 integration tests for complete pipeline
- Comprehensive feature documentation (docs/FEATURES.md)

## [0.3.0] - 2026-01-13

### Added
- Configuration system with immutable risk limits
- Exchange API configuration with credential validation
- SQLite database schema for all system data
- Configuration validation tests
- Database initialization script

### Security
- Risk limits enforced as frozen dataclasses (immutable)
- API credentials loaded from environment only
- No hardcoded secrets in code

## [0.2.0] - 2026-01-14

### Added
- Python environment setup with pinned dependencies
- Virtual environment configuration
- Environment variable template (.env.example)
- Environment validation tests
- Setup documentation

## [0.1.0] - 2026-01-14

### Added
- Initial repository structure
- README with system philosophy
- PHILOSOPHY.md with risk awareness
- Complete folder structure for modular design
- .gitignore for Python, secrets, and logs

[Unreleased]: https://github.com/Katiehey/Crypto-Survival-System/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Katiehey/Crypto-Survival-System/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Katiehey/Crypto-Survival-System/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Katiehey/Crypto-Survival-System/releases/tag/v0.1.0

### Planned for Day 3
- Regime classifier (rule-based)
- Regime confidence scoring
- Regime visualization

## [0.7.0] - 2026-01-15 - Day 2 Complete

### Added
- ATR (Average True Range) calculation with percentile tracking
- Efficiency Ratio (Kaufman) for trend strength measurement
- Volume metrics (MA, ratio, percentile, regime classification)
- Volume spike detection
- Unified feature calculation pipeline
- Complete feature validation system
- Feature summary statistics
- CSV export functionality
- 57+ comprehensive tests (all passing)
- Feature documentation (FEATURES.md)
- Day 2 summary document

### Technical Details
- 19 calculated features across 3 categories
- Mathematical correctness validated with known values
- Edge case handling (zeros, NaN, infinites)
- Deterministic calculations (reproducible results)
- Real data compatibility tested

### Test Coverage
- ATR tests: 13
- Efficiency tests: 17
- Volume tests: 18
- Integration tests: 9
- Total: 57+ tests, 100% passing

## [0.6.0] - 2026-01-15 - Feature Pipeline Integration

## [0.5.0] - 2026-01-15 - Day 1 Complete

### Added
- Regime classifier with 4 regime types (TREND, RANGE, CHAOS, NO_TRADE)
- Rule-based classification logic using feature thresholds
- Confidence scoring for regime classifications
- Tradability flag for each regime
- DataFrame batch classification
- Regime statistics calculation
- 15 comprehensive classifier tests (all passing)

### Added
- Complete regime pipeline integration (data → features → regime)
- Regime classification validation
- End-to-end pipeline tests (12 tests)
- Regime analysis script for real data
- Pipeline function with automatic validation

### Added
- Regime transition detection and analysis
- Regime duration statistics
- Regime transition matrix (probability matrix)
- Regime persistence calculation
- Text-based regime timeline visualization
- Complete regime sequence analysis
- 13 visualization tests (all passing)
- Regime classification documentation

### Planned for Days 4-5 (Week 1 Completion)
- End-to-end integration testing
- Performance benchmarking
- Code quality review
- Week 1 retrospective
- Week 2 detailed planning

## [0.8.0] - 2026-01-16 - Day 3 Complete: Regime Classification

### Added
- Rule-based regime classifier (4 regime types)
- Regime confidence scoring system
- Complete pipeline integration (OHLCV → Features → Regime)
- Regime transition detection and analysis
- Regime duration statistics
- Regime transition probability matrix
- Regime persistence metrics
- Text-based regime timeline visualization
- Complete regime sequence analysis tools
- Regime analysis script for real data
- 40 new tests (85+ total, all passing)
- Regime classification documentation
- Day 3 summary document

### Regime Types
- TREND: Strong directional movement (tradable)
- RANGE: Sideways consolidation (tradable)
- CHAOS: High volatility without direction (avoid)
- NO_TRADE: Unclear/dangerous conditions (avoid)

### Classification Features
- Confidence scoring (0-1)
- Tradability determination
- Reasoning for each classification
- Automatic validation
- Batch classification support

### Analysis Capabilities
- Transition detection
- Duration calculations
- Transition matrices
- Persistence metrics
- Timeline visualization
- Complete statistics

### Technical Details
- Rule-based logic (no AI in classification)
- Deterministic outputs
- Configurable thresholds
- Comprehensive error handling
- Full validation pipeline

## [0.7.0] - 2026-01-16 - Day 2 Complete: Feature Engineering

### Added
- Comprehensive system integration tests (15 tests)
- System health check script
- Integration test report documentation
- Multi-scenario validation (trending, ranging, chaotic markets)
- Edge case testing (missing data, minimal data, extreme volatility)
- Reproducibility validation

### Added
- Performance benchmarking script
- Scalability testing across dataset sizes (50-1000 candles)
- Memory usage profiling
- Individual feature timing analysis
- Performance report documentation

### Performance Results
- 200 candles processed in ~250ms (4x faster than target)
- Memory usage: ~12MB (8x less than limit)
- Near-linear scaling (O(n) complexity)
- No optimization required

### Added - Week 2, Day 6
- Risk engine foundation (position sizing)
- Fixed fractional position sizing calculation
- Position size validation logic
- 13 position sizing tests (all passing)
- Mathematical verification of calculations

### Added - Week 2, Day 6
- Trade validation system (4 risk gates)
- Trade state tracking (daily limits, consecutive losses)
- Kill switch activation/deactivation
- Trade recording and state updates
- 13 validation tests (all passing)

### Added - Week 2, Day 6
- CapitalTracker class for drawdown monitoring
- Peak capital tracking
- Drawdown calculation (percentage and amount)
- Automatic kill switch on 5% drawdown
- Capital statistics and reporting
- Integration with RiskEngine
- 16 capital tracking tests (all passing)

### Added - Week 2, Day 6
- Cooldown period after consecutive losses (24h)
- Automatic cooldown activation/clearing
- Comprehensive risk engine status reporting
- Complete risk engine integration tests
- Risk engine print_status() method
- 10 integration tests (all passing)

### Completed - Week 2, Day 6
- Complete risk engine with all features
- Position sizing ✓
- Multi-gate validation ✓
- Capital tracking ✓
- Drawdown monitoring ✓
- Daily limits ✓
- Cooldown periods ✓
- Kill switch ✓
- 52+ tests (all passing)
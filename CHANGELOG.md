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

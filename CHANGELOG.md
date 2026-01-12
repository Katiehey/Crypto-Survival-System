# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-01-07

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

## [0.2.0] - 2026-01-07

### Added
- Python environment setup with pinned dependencies
- Virtual environment configuration
- Environment variable template (.env.example)
- Environment validation tests
- Setup documentation

## [0.1.0] - 2026-01-07

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
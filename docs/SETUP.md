# Setup Instructions

## Prerequisites

- Python 3.10 or higher
- Git
- Binance account (for live/testnet trading)
- ~500MB disk space

## Initial Setup

### 1. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/crypto-survival-system.git
cd crypto-survival-system
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 5. Verify Installation
```bash
pytest tests/test_environment.py -v
```

All tests should pass.

## Binance API Key Setup (When Ready)

1. Log in to Binance
2. Go to API Management
3. Create new API key
4. **Enable**: Spot & Margin Trading ONLY
5. **Disable**: Withdrawals, Futures, Margin
6. Enable IP whitelist (recommended)
7. Save API key and secret to `.env`

## Daily Activation

Each time you work on the project:
```bash
cd crypto-survival-system
source venv/bin/activate  # activate virtual environment
```

## Troubleshooting

### Virtual environment not activating
- Check you're in project root
- Recreate: `rm -rf venv && python3 -m venv venv`

### Import errors
- Ensure venv is activated (prompt should show `(venv)`)
- Reinstall: `pip install -r requirements.txt`

### Tests failing
- Check Python version: `python --version` (must be 3.10+)
- Check dependencies: `pip list`
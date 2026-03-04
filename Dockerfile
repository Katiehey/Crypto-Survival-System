FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . /app

# Install python deps
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir ccxt

ENV PYTHONUNBUFFERED=1

# Default command: run status snapshot (safe). Override to run full canary.
CMD ["python3", "scripts/write_status_snapshot.py", "--model-dir", "models/production/production_retrained_winsor_quantile_long"]

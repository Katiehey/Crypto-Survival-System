# VPS Provisioning & Canary Deployment (Oracle Cloud / Any Ubuntu)

This document provides a minimal, low-cost path to run the canary on an always-free VPS (Oracle Cloud, Hetzner, DigitalOcean, etc.). It includes scripts and systemd unit to get you started.

Prereqs (on your local machine)
- A GitHub Personal Access Token (if you want remote dispatch)
- SSH key for the VPS

Quick steps (recommended)

1. SSH into your VPS and install prerequisites:

```bash
# on VPS (Ubuntu)
sudo apt update && sudo apt install -y git curl
```

2. Copy repository (or clone) and create `.env` from template:

```bash
git clone https://github.com/Katiehey/Crypto-Survival-System.git /opt/crypto-survival-system
cd /opt/crypto-survival-system
cp .env.template .env
# edit .env and fill secrets
```

3. Use the provided helper to provision Docker and start the canary:

```bash
sudo ./scripts/provision_vps.sh /opt/crypto-survival-system
```

4. Optional — register a systemd unit (if you prefer systemd instead of docker-compose):

```bash
sudo cp deploy/canary.service /etc/systemd/system/canary.service
sudo systemctl daemon-reload
sudo systemctl enable --now canary.service
journalctl -u canary.service -f
```

Notes & security
- Keep `.env` out of git. The repository contains a CI preflight that fails if `.env` is tracked.
- Use environment-based secrets in production (systemd `EnvironmentFile=` or Docker secrets) rather than committing `.env`.

Troubleshooting
- If the canary fails due to missing Python imports, ensure `PYTHONPATH=.` is set in the environment or use the container (the Dockerfile included in the repo is the easiest).

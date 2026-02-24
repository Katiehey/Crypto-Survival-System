"""Simple alerting utilities (Telegram) for monitoring.

This module keeps external deps minimal by using the stdlib `urllib`.
Configure with environment variables:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_ENABLED` (optional, default true)

If no token/chat are present the functions will log and return False.
"""
import os
from dotenv import load_dotenv, find_dotenv

# Ensure .env is loaded so TELEGRAM_* vars are available when this module is imported
load_dotenv(find_dotenv(usecwd=True), override=False)
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_telegram_config() -> Optional[dict]:
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    enabled = os.getenv('TELEGRAM_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    if not enabled:
        return None
    if not token or not chat_id:
        logger.info('Telegram not configured (missing token/chat id)')
        return None
    return {'token': token, 'chat_id': chat_id}


def send_telegram_alert(message: str, parse_mode: str = 'Markdown') -> bool:
    """Send a Telegram message via Bot API.

    Returns True on success, False otherwise. Non-fatal on failure.
    """
    cfg = _get_telegram_config()
    if not cfg:
        logger.debug('Telegram alert skipped (not configured)')
        return False

    import time
    try:
        import urllib.request

        url = f"https://api.telegram.org/bot{cfg['token']}/sendMessage"
        payload = {
            'chat_id': cfg['chat_id'],
            'text': message,
            'parse_mode': parse_mode,
        }
        data = json.dumps(payload).encode('utf-8')

        max_attempts = 3
        backoff = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = resp.read().decode('utf-8')
                    logger.info('Telegram alert sent')
                    return True
            except Exception as e:
                logger.warning(f'Telegram send attempt {attempt} failed: {e}')
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.exception('All Telegram send attempts failed')
                    return False
    except Exception as e:
        logger.exception(f'Failed to prepare Telegram request: {e}')
        return False

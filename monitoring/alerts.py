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
        import urllib.error

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
            except urllib.error.HTTPError as he:
                # Read and log Telegram API error response body for debugging (400/401 etc.)
                try:
                    body = he.read().decode('utf-8', errors='replace')
                except Exception:
                    body = '<unable to read body>'
                logger.warning(f'Telegram HTTPError (attempt {attempt}): {he.code} {he.reason} - {body}')

                # Common cause: message entity parse errors when using Markdown.
                # Attempt an immediate fallback send without `parse_mode` (plain text).
                if "can't parse entities" in body.lower():
                    logger.info('Telegram parse error detected; retrying without parse_mode')
                    try:
                        payload_no_mode = payload.copy()
                        payload_no_mode.pop('parse_mode', None)
                        data_no_mode = json.dumps(payload_no_mode).encode('utf-8')
                        req2 = urllib.request.Request(url, data=data_no_mode, headers={'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req2, timeout=10) as resp2:
                            resp2.read()
                            logger.info('Telegram alert sent (fallback without parse_mode)')
                            return True
                    except Exception as e2:
                        logger.warning(f'Fallback send without parse_mode failed: {e2}')

                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error('All Telegram send attempts failed (HTTPError)')
                    return False
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

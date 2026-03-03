#!/usr/bin/env python3
"""Send CI PSI report summary to Telegram chat (if credentials provided).

Reads `backtest_results/ci_psi_report.json` and posts a short summary.
Requires env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import json
import os
import sys

REPORT = 'backtest_results/ci_psi_report.json'


def post_telegram(token: str, chat_id: str, text: str) -> bool:
    try:
        import requests
    except Exception:
        print('requests not available; cannot post to Telegram')
        return False
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    resp = requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})
    return resp.ok


def summarize(report: dict) -> str:
    overall = report.get('overall_status', 'UNKNOWN')
    features = report.get('features', {})
    top = sorted([(k, v.get('psi') or 0.0) for k, v in features.items()], key=lambda x: -x[1])[:5]
    lines = [f'*CI PSI*: {overall}']
    lines.append('Top features by PSI:')
    for k, v in top:
        lines.append(f'- {k}: {v:.3f}')
    return '\n'.join(lines)


def main():
    if not os.path.exists(REPORT):
        print('No CI PSI report found:', REPORT)
        sys.exit(0)
    with open(REPORT, 'r') as f:
        report = json.load(f)
    text = summarize(report)
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat:
        print('TELEGRAM credentials not set; printing summary:')
        print(text)
        return
    ok = post_telegram(token, chat, text)
    if not ok:
        print('Failed to post to Telegram')


if __name__ == '__main__':
    main()

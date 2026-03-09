#!/usr/bin/env python3
"""Check that the CI/production DB contains a `candles` table with rows.

Exits 0 when OK. Exits 2 when table missing, 3 when too few rows, 1 on other errors.
"""
import sqlite3
import os
import sys

DB_PATH = os.getenv('DB_PATH', 'data/trading.db')
MIN_ROWS = int(os.getenv('DB_MIN_ROWS', '10'))


def main():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return 1
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candles'")
        r = cur.fetchone()
        if not r:
            print('Table `candles` not found in DB')
            return 2
        cur.execute('SELECT COUNT(1) FROM candles')
        cnt = cur.fetchone()[0]
        print(f'candles rows: {cnt}')
        if cnt < MIN_ROWS:
            print(f'Not enough rows in candles (found {cnt}, need {MIN_ROWS})')
            return 3
        print('DB check passed')
        return 0
    except Exception as e:
        print('DB check error:', e)
        return 1


if __name__ == '__main__':
    sys.exit(main())

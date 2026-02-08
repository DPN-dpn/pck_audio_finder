import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'app.log'


def open_log_file(mode='ab'):
    return open(LOG_FILE, mode)


def write_start(action):
    try:
        from datetime import datetime
        with open(LOG_FILE, 'a', encoding='utf-8') as lf:
            lf.write(f"--- {action} started: {datetime.now().isoformat()} ---\n")
    except Exception:
        pass


def write_stop(action):
    try:
        from datetime import datetime
        msg = f"--- {action} stopped by user: {datetime.now().isoformat()} ---\n"
        with open(LOG_FILE, 'ab') as lf:
            lf.write(msg.encode('utf-8'))
    except Exception:
        pass


def read_tail(max_chars=20000, encodings=None):
    if encodings is None:
        encodings = ['utf-8', 'cp949', 'latin1']
    if not LOG_FILE.exists():
        return ''
    data = ''
    for enc in encodings:
        try:
            with open(LOG_FILE, 'r', encoding=enc, errors='strict') as f:
                data = f.read()
            break
        except UnicodeDecodeError:
            continue
        except Exception:
            continue

    if not data:
        try:
            with open(LOG_FILE, 'r', encoding='latin1', errors='replace') as f:
                data = f.read()
        except Exception:
            return ''

    return data[-max_chars:]

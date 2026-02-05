import subprocess
import threading
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'transcribe.log'

_proc = None
_lock = threading.Lock()


def _monitor_proc(cmd, cwd):
    global _proc
    with open(LOG_FILE, 'ab') as lf:
        _proc = subprocess.Popen(cmd, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT)
        _proc.wait()
    _proc = None


def start_transcription(input_dir='input', tsv='results.tsv', model='small', device='cpu', runtime='runtime'):
    global _proc
    with _lock:
        if _proc is not None and _proc.poll() is None:
            return False
        runtime_python = ROOT / runtime / 'python.exe'
        if not runtime_python.exists():
            runtime_python = Path(sys.executable)

        cmd = [str(runtime_python), str(ROOT / 'app' / 'transcribe.py'),
               '--input', str(input_dir), '--tsv', str(tsv),
               '--model', model, '--device', device, '--runtime', runtime]

        # clear previous log
        if LOG_FILE.exists():
            try:
                LOG_FILE.unlink()
            except Exception:
                pass

        t = threading.Thread(target=_monitor_proc, args=(cmd, str(ROOT)), daemon=True)
        t.start()
        return True


def get_status():
    running = False
    with _lock:
        if _proc is not None and _proc.poll() is None:
            running = True

    tail = ''
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                data = f.read()
                tail = data[-20000:]
        except Exception:
            tail = ''
    return {'running': running, 'log': tail}


def stop_transcription():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            try:
                _proc.terminate()
                return True
            except Exception:
                return False
    return False

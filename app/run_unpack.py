import subprocess
import threading
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'unpack.log'

_proc = None
_lock = threading.Lock()


def _monitor_proc(cmd, cwd, env=None):
    global _proc
    with open(LOG_FILE, 'ab') as lf:
        _proc = subprocess.Popen(cmd, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, env=env)
        _proc.wait()
    _proc = None


def start_unpack(input_dir='input', out_base='unpacked', runtime=None, workers=0):
    global _proc
    with _lock:
        if _proc is not None and _proc.poll() is None:
            return False

        runtime_python = ROOT / runtime / 'python.exe' if runtime else Path(sys.executable)
        if runtime and not runtime_python.exists():
            runtime_python = Path(sys.executable)

        cmd = [str(runtime_python), str(ROOT / 'app' / 'unpack_pck.py'),
               '--input', str(input_dir), '--output', str(out_base), '--workers', str(workers)]

        # clear previous log and write header
        try:
            from datetime import datetime
            with open(LOG_FILE, 'w', encoding='utf-8') as lf:
                lf.write(f"--- unpack started: {datetime.now().isoformat()} ---\n")
        except Exception:
            try:
                if LOG_FILE.exists():
                    LOG_FILE.unlink()
            except Exception:
                pass

        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        t = threading.Thread(target=_monitor_proc, args=(cmd, str(ROOT), env), daemon=True)
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
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    data = f.read()
            except UnicodeDecodeError:
                try:
                    with open(LOG_FILE, 'r', encoding='cp949') as f:
                        data = f.read()
                except Exception:
                    with open(LOG_FILE, 'r', encoding='latin1', errors='replace') as f:
                        data = f.read()
            tail = data[-20000:]
        except Exception:
            tail = ''
    return {'running': running, 'log': tail}


def stop_unpack():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            try:
                try:
                    from datetime import datetime
                    msg = f"--- unpack stopped by user: {datetime.now().isoformat()} ---\n"
                    with open(LOG_FILE, 'ab') as lf:
                        lf.write(msg.encode('utf-8'))
                except Exception:
                    pass
                _proc.terminate()
                return True
            except Exception:
                return False
    return False


if __name__ == '__main__':
    # simple CLI for debugging
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='input')
    parser.add_argument('--output', default='unpacked')
    parser.add_argument('--runtime', default=None)
    parser.add_argument('--workers', type=int, default=0)
    args = parser.parse_args()
    start_unpack(args.input, args.output, args.runtime, args.workers)

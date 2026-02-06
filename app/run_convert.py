import subprocess
import threading
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'convert.log'

_proc = None
_lock = threading.Lock()


def _monitor_proc(cmd, cwd, env=None):
    global _proc
    with open(LOG_FILE, 'ab') as lf:
        _proc = subprocess.Popen(cmd, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, env=env)
        _proc.wait()
    _proc = None


def start_convert(input_dir='input', site_packages=None, workers=1, overwrite=False, runtime=None):
    global _proc
    with _lock:
        if _proc is not None and _proc.poll() is None:
            return False

        runtime_python = ROOT / runtime / 'python.exe' if runtime else Path(sys.executable)
        if runtime and not runtime_python.exists():
            runtime_python = Path(sys.executable)

        cmd = [str(runtime_python), str(ROOT / 'app' / 'convert_wem.py'),
               '--input', str(input_dir), '--site-packages', str(site_packages or os.path.join('runtime', 'Lib', 'site-packages')),
               '--workers', str(workers)]
        if overwrite:
            cmd.append('--overwrite')

        # clear previous log and write header
        try:
            from datetime import datetime
            with open(LOG_FILE, 'w', encoding='utf-8') as lf:
                lf.write(f"--- convert started: {datetime.now().isoformat()} ---\n")
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


def stop_convert():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            try:
                try:
                    from datetime import datetime
                    msg = f"--- convert stopped by user: {datetime.now().isoformat()} ---\n"
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='input')
    parser.add_argument('--site-packages', default=os.path.join('runtime', 'Lib', 'site-packages'))
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--runtime', default=None)
    args = parser.parse_args()
    start_convert(args.input, args.site_packages, args.workers, args.overwrite, args.runtime)

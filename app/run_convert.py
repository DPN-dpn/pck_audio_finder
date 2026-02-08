import subprocess
import threading
import os
import sys
from pathlib import Path
import logging_helper as lg

ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = lg.LOG_FILE

_proc = None
_lock = threading.Lock()


def _monitor_proc(cmd, cwd, env=None):
    global _proc
    lf = None
    try:
        lf = lg.open_log_file('ab')
        _proc = subprocess.Popen(cmd, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, env=env)
        _proc.wait()
    finally:
        _proc = None
        if lf:
            try:
                lf.close()
            except Exception:
                pass


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

        # append start header (do not erase previous logs)
        lg.write_start('convert')

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

    tail = lg.read_tail(20000)
    return {'running': running, 'log': tail}


def stop_convert():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            try:
                try:
                    lg.write_stop('convert')
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

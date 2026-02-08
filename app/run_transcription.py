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

        # append start header (do not erase previous logs)
        lg.write_start('transcription')

        # Ensure child python uses UTF-8 output to avoid encoding garble on Windows.
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'
        # Explicit IO encoding for spawned process
        env['PYTHONIOENCODING'] = 'utf-8'
        # Tell child process not to append directly to the log file
        env['TRANSCRIBE_SKIP_CHILD_LOG'] = '1'

        t = threading.Thread(target=_monitor_proc, args=(cmd, str(ROOT), env), daemon=True)
        t.start()
        return True


def get_status():
    running = False
    with _lock:
        if _proc is not None and _proc.poll() is None:
            running = True

    tail = lg.read_tail(20000, encodings=['utf-8', 'cp949', 'euc-kr', 'latin1'])
    return {'running': running, 'log': tail}


def stop_transcription():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            try:
                # Write stop marker to log so UI can display it immediately
                try:
                    lg.write_stop('transcription')
                except Exception:
                    pass

                _proc.terminate()
                return True
            except Exception:
                return False
    return False

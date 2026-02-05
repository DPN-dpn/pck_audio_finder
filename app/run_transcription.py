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


def _monitor_proc(cmd, cwd, env=None):
    global _proc
    with open(LOG_FILE, 'ab') as lf:
        _proc = subprocess.Popen(cmd, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, env=env)
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

        # clear previous log and write start header so UI shows a fresh log
        try:
            from datetime import datetime
            with open(LOG_FILE, 'w', encoding='utf-8') as lf:
                lf.write(f"--- transcription started: {datetime.now().isoformat()} ---\n")
        except Exception:
            # fallback: attempt to remove the file
            try:
                if LOG_FILE.exists():
                    LOG_FILE.unlink()
            except Exception:
                pass

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

    tail = ''
    if LOG_FILE.exists():
        try:
            # Prefer UTF-8, but fall back to common Windows encodings if file is CP949 (ANSI)
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    data = f.read()
            except UnicodeDecodeError:
                try:
                    with open(LOG_FILE, 'r', encoding='cp949') as f:
                        data = f.read()
                except Exception:
                    try:
                        with open(LOG_FILE, 'r', encoding='euc-kr') as f:
                            data = f.read()
                    except Exception:
                        # last resort: latin1 -> preserves bytes
                        with open(LOG_FILE, 'r', encoding='latin1', errors='replace') as f:
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
                # Write stop marker to log so UI can display it immediately
                try:
                    from datetime import datetime
                    msg = f"--- transcription stopped by user: {datetime.now().isoformat()} ---\n"
                    with open(LOG_FILE, 'ab') as lf:
                        lf.write(msg.encode('utf-8'))
                except Exception:
                    pass

                _proc.terminate()
                return True
            except Exception:
                return False
    return False

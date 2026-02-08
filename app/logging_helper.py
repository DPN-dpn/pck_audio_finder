import subprocess
import threading
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'app.log'

# Internal lock to serialize writes to the log file
_write_lock = threading.Lock()

# (previously had subscriber queues here; now simplified to a notification event)

# Simple notification event for GUI: set when new data appended
_notify_event = threading.Event()


def _append_text(text: str):
    try:
        with _write_lock:
            with open(LOG_FILE, 'a', encoding='utf-8', errors='replace', newline='') as lf:
                lf.write(text)
                lf.flush()
    except Exception:
        # best-effort only; do not raise
        pass
    # notify any waiter (e.g., GUI) that new data is available
    try:
        _notify_event.set()
    except Exception:
        pass


def log(msg: str):
    """Append a message to the central log. Ensures newline termination."""
    if msg is None:
        return
    if not msg.endswith('\n'):
        msg = msg + '\n'
    _append_text(msg)


def write_start(action: str):
    _append_text(f"--- {action} started: {datetime.now().isoformat()} ---\n")


def write_stop(action: str):
    _append_text(f"--- {action} stopped by user: {datetime.now().isoformat()} ---\n")


def read_tail(max_chars: int = 20000, encodings=None) -> str:
    if encodings is None:
        encodings = ['utf-8', 'cp949', 'euc-kr', 'latin1']
    try:
        if not LOG_FILE.exists():
            return ''

        # Read as binary then decode from best encoding
        with open(LOG_FILE, 'rb') as f:
            # read at most max_chars bytes from end for efficiency
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - max_chars - 1024)
            f.seek(start)
            raw = f.read()

        for enc in encodings:
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode('utf-8', errors='replace')
    except Exception:
        return ''


def read_all(encodings=None) -> str:
    """Read entire log file, trying several encodings."""
    if encodings is None:
        encodings = ['utf-8', 'cp949', 'euc-kr', 'latin1']
    try:
        if not LOG_FILE.exists():
            return ''
        raw = None
        with open(LOG_FILE, 'rb') as f:
            raw = f.read()
        for enc in encodings:
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode('utf-8', errors='replace')
    except Exception:
        return ''


def read_from(pos: int = 0, encodings=None) -> tuple:
    """Read bytes from `pos` to EOF and return (decoded_text, new_pos).

    Decoding tries several encodings similar to `read_all`.
    """
    if encodings is None:
        encodings = ['utf-8', 'cp949', 'euc-kr', 'latin1']
    try:
        if not LOG_FILE.exists():
            return ('', 0)
        with open(LOG_FILE, 'rb') as f:
            f.seek(pos)
            raw = f.read()
            newpos = f.tell()

        if not raw:
            return ('', newpos)

        for enc in encodings:
            try:
                return (raw.decode(enc), newpos)
            except Exception:
                continue
        return (raw.decode('utf-8', errors='replace'), newpos)
    except Exception:
        return ('', pos)


def wait_notification(timeout: float = None) -> bool:
    """Wait until new log data is available or timeout. Clears the event on return True."""
    try:
        got = _notify_event.wait(timeout)
        if got:
            # clear so next wait will block until new event
            _notify_event.clear()
        return bool(got)
    except Exception:
        return False


def monitor_in_thread(cmd, cwd, env=None, action='task', on_proc_set=None):
    """Run subprocess in a background thread and append its output to the central log file.

    Each line of stdout/stderr is decoded (utf-8, cp949, latin1 fallback) and written
    to `logs/app.log`. `on_proc_set` if provided will be called with the Popen object
    when started and with None when finished.
    """
    def _runner():
        proc = None
        try:
            proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            if callable(on_proc_set):
                try:
                    on_proc_set(proc)
                except Exception:
                    pass

            if proc.stdout is None:
                proc.wait()
                return

            # Read stdout line-by-line
            while True:
                chunk = proc.stdout.readline()
                if not chunk:
                    if proc.poll() is not None:
                        break
                    continue
                # chunk is bytes; decode robustly
                try:
                    text = chunk.decode('utf-8')
                except Exception:
                    try:
                        text = chunk.decode('cp949')
                    except Exception:
                        text = chunk.decode('latin1', errors='replace')
                _append_text(text)

            proc.wait()
        finally:
            if callable(on_proc_set):
                try:
                    on_proc_set(None)
                except Exception:
                    pass

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return t


# subscribe/unsubscribe removed — GUI uses wait_notification()/read_all()

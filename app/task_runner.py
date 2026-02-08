import threading
from pathlib import Path
import logging_helper as lg


class TaskProcess:
    def __init__(self, action: str):
        self.action = action
        self._proc = None
        self._lock = threading.Lock()

    def start(self, cmd, cwd, env=None, start_header: bool = True):
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return False
            if start_header:
                try:
                    lg.log(f"--- {self.action} started: {lg.datetime.now().isoformat()} ---")
                except Exception:
                    pass

            def _set_proc(p):
                with self._lock:
                    self._proc = p

            lg.monitor_in_thread(cmd, cwd, env=env, action=self.action, on_proc_set=_set_proc)
            return True

    def get_status(self, tail_chars: int = 20000):
        running = False
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                running = True
        tail = lg.read_tail(tail_chars)
        return {'running': running, 'log': tail}

    def stop(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    try:
                        lg.log(f"--- {self.action} stopped by user: {lg.datetime.now().isoformat()} ---")
                    except Exception:
                        pass
                    self._proc.terminate()
                    return True
                except Exception:
                    return False
        return False

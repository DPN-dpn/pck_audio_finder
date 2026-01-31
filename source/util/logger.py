"""
Simple GUI logger module.

Usage:
  from util import logger
  logger.attach(text_widget)  # Text widget from tkinter
  logger.log("CATEGORY", "message")

The module buffers messages until a Text widget is attached. Logging is scheduled
via widget.after(...) so it is safe to call from worker threads.
"""

import threading

_widget = None
_buffer = []
_lock = threading.Lock()


def attach(text_widget) -> None:
    """Attach a tkinter.Text widget to receive logs. Flushes any buffered messages."""
    global _widget
    with _lock:
        _widget = text_widget
        # copy and clear buffer while holding lock
        buf = list(_buffer)
        _buffer.clear()
    # flush buffer outside the lock to avoid deadlocks
    if buf and _widget is not None:
        try:
            for line in buf:
                _safe_insert(line)
        finally:
            buf.clear()


def _safe_insert(text: str) -> None:
    """Insert text into the widget using after to ensure thread-safety."""
    global _widget
    if _widget is None:
        return

    def _do():
        try:
            _widget.insert("end", text)
            _widget.see("end")
        except Exception:
            # widget might have been destroyed
            pass

    try:
        _widget.after(0, _do)
    except Exception:
        # if after fails, fallback to direct insert (best-effort)
        try:
            _do()
        except Exception:
            pass


def log(category: str, message: str) -> None:
    """Log a message under a category. Message will be formatted and sent to the attached widget or buffered."""
    if not category:
        category = ""
    text = f"[{category}] {message}\n"
    with _lock:
        if _widget is None:
            _buffer.append(text)
            return
    # insert outside the lock to avoid deadlocks if widget callbacks log again
    _safe_insert(text)


def clear_buffer() -> None:
    """Clear any buffered messages (not the widget contents)."""
    with _lock:
        _buffer.clear()

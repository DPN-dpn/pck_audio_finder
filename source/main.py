import tkinter as tk
from tkinter import ttk
from ui.layout import build_layout
from ui import a_page, b_page
from util import logger
from util import config as _config

# Ensure bundled third-party tools are present (download if missing)
from util.lib_installer import ensure_libs


def run():
    # download required libs if missing (non-blocking could be added later)
    ensure_libs()

    root = tk.Tk()
    root.title("PCK Audio Finder")

    # Restore saved window size if available
    try:
        _config.ensure_config()
        saved_w = _config.get_int('ui', 'window_width', fallback=0)
        saved_h = _config.get_int('ui', 'window_height', fallback=0)
        if saved_w and saved_h:
            root.geometry(f"{saved_w}x{saved_h}")
        else:
            root.geometry("900x650")
    except Exception:
        root.geometry("900x650")

    # Debounced save of window size on resize
    try:
        def _schedule_save(e=None):
            try:
                if getattr(root, '_save_after_id', None):
                    root.after_cancel(root._save_after_id)

                def _do_save():
                    try:
                        w = root.winfo_width()
                        h = root.winfo_height()
                        _config.set_int('ui', 'window_width', int(w))
                        _config.set_int('ui', 'window_height', int(h))
                    except Exception:
                        pass

                root._save_after_id = root.after(500, _do_save)
            except Exception:
                pass

        root.bind('<Configure>', _schedule_save)

        def _on_close():
            try:
                w = root.winfo_width()
                h = root.winfo_height()
                _config.set_int('ui', 'window_width', int(w))
                _config.set_int('ui', 'window_height', int(h))
            except Exception:
                pass
            try:
                root.destroy()
            except Exception:
                pass

        root.protocol('WM_DELETE_WINDOW', _on_close)
    except Exception:
        pass

    # Build overall layout (switch buttons, container frames, shared log)
    tab_a, tab_b, log = build_layout(root)

    # Attach the Text widget to the logger module so other modules can log easily
    logger.attach(log)

    # Build A and B pages
    a_page.build(tab_a)
    b_page.build(tab_b)

    root.mainloop()


if __name__ == "__main__":
    run()

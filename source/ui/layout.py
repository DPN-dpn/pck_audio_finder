import tkinter as tk
from tkinter import ttk
from util import config as _config


def build_layout(root):
    """Create switch buttons, container with two frames, and a shared log widget.

    Uses a vertical PanedWindow so the log pane is resizable by dragging the sash.
    Returns (tab_a_frame, tab_b_frame, log_text_widget).
    """
    # Ensure config exists and get saved log height (pixels)
    _config.ensure_config()
    saved_log_h = _config.get_int("ui", "log_height", fallback=120)

    # Paned window splits main area (top) and log (bottom)
    paned = ttk.PanedWindow(root, orient=tk.VERTICAL)
    paned.pack(fill="both", expand=True, padx=6, pady=6)

    # Top pane: switch buttons + container
    top_pane = ttk.Frame(paned)
    paned.add(top_pane, weight=1)

    switch_frame = ttk.Frame(top_pane)
    switch_frame.pack(fill="x")

    container = ttk.Frame(top_pane)
    container.pack(fill="both", expand=True)

    tab_a = ttk.Frame(container)
    tab_b = ttk.Frame(container)

    for f in (tab_a, tab_b):
        f.place(relx=0, rely=0, relwidth=1, relheight=1)

    import tkinter as _tk

    def show(tab_name):
        if tab_name == "A":
            tab_a.lift()
            btn_a.config(relief="sunken")
            btn_b.config(relief="raised")
        else:
            tab_b.lift()
            btn_b.config(relief="sunken")
            btn_a.config(relief="raised")

    btn_a = _tk.Button(switch_frame, text="A", command=lambda: show("A"))
    btn_b = _tk.Button(switch_frame, text="B", command=lambda: show("B"))

    btn_a.pack(side="left", fill="x", expand=True)
    btn_b.pack(side="left", fill="x", expand=True)

    # Default to A
    btn_a.config(relief="sunken")
    tab_a.lift()

    # Bottom pane: log
    bottom_pane = ttk.Frame(paned)
    paned.add(bottom_pane, weight=0)
    try:
        paned.paneconfigure(bottom_pane, minsize=40)
    except Exception:
        pass

    log = tk.Text(bottom_pane)
    log.pack(fill="both", expand=True)

    # After geometry has been applied, set the sash so bottom pane has saved height.
    # Use a short retry loop with `after` because initial geometry may not be ready yet.
    def _attempt_set_sash(retries=8):
        try:
            paned.update_idletasks()
            paned_h = paned.winfo_height()
            if paned_h <= 1 and retries > 0:
                root.after(40, lambda: _attempt_set_sash(retries - 1))
                return
            if paned_h <= 1:
                paned_h = int(root.winfo_screenheight() * 0.6)
            top_h = max(0, int(paned_h) - int(saved_log_h))
            paned.sashpos(0, top_h)
        except Exception:
            pass

    root.after(40, _attempt_set_sash)

    # Save log height when user finishes dragging the sash
    def _on_release(event=None):
        try:
            toppos = paned.sashpos(0)
            cur_total = root.winfo_height()
            log_h = max(0, cur_total - toppos)
            _config.set_int("ui", "log_height", int(log_h))
        except Exception:
            pass

    paned.bind("<ButtonRelease-1>", _on_release)

    return tab_a, tab_b, log

import tkinter as tk
from tkinter import ttk
from pathlib import Path

class ProgressOverlay:
    def __init__(self, parent, debounce_ms=100):
        self.parent = parent
        self.debounce_ms = debounce_ms
        self.overlay = {'win': None, 'bar': None, 'label': None}
        self._throttle_scheduled = False
        self._throttle_last = {'frac': 0.0, 'msg': None}

    def _create_overlay(self):
        root = self.parent.winfo_toplevel()
        ow = tk.Toplevel(root)
        ow.overrideredirect(True)
        try:
            ow.transient(root)
        except Exception:
            pass
        try:
            x = root.winfo_rootx()
            y = root.winfo_rooty()
            w = root.winfo_width()
            h = root.winfo_height()
            ow.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass
        ow.attributes('-topmost', True)
        try:
            ow.wm_attributes('-alpha', 0.6)
        except Exception:
            pass
        frm = ttk.Frame(ow)
        frm.place(relx=0.5, rely=0.5, anchor='center')
        lbl = ttk.Label(frm, text="작업 중...")
        lbl.pack(padx=8, pady=(0,6))
        pb = ttk.Progressbar(frm, orient='horizontal', length=300, mode='determinate')
        pb.pack(padx=8, pady=6)
        self.overlay['win'] = ow
        self.overlay['bar'] = pb
        self.overlay['label'] = lbl

        # reposition when root moves/resizes
        def _on_root_config(event=None):
            try:
                if not self.overlay['win']:
                    return
                try:
                    st = root.state()
                    if st == 'iconic':
                        self.overlay['win'].withdraw()
                        return
                except Exception:
                    pass
                x = root.winfo_rootx()
                y = root.winfo_rooty()
                w = root.winfo_width()
                h = root.winfo_height()
                self.overlay['win'].geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                pass

        try:
            root.bind('<Configure>', _on_root_config)
        except Exception:
            pass

    def show(self, message="작업 중...", maximum=None, indeterminate=False):
        if self.overlay['win'] is None:
            self._create_overlay()
        try:
            self.overlay['label'].config(text=message)
            if indeterminate:
                self.overlay['bar'].config(mode='indeterminate')
                self.overlay['bar'].start(10)
            else:
                self.overlay['bar'].config(mode='determinate')
                if maximum is not None:
                    self.overlay['bar']['maximum'] = maximum
                self.overlay['bar']['value'] = 0
            self.overlay['win'].deiconify()
            self.overlay['win'].lift()
        except Exception:
            pass

    def update(self, value, message=None):
        try:
            if self.overlay['bar']:
                self.overlay['bar']['value'] = value
            if message and self.overlay['label']:
                self.overlay['label'].config(text=message)
        except Exception:
            pass

    def hide(self):
        try:
            if self.overlay['bar'] and self.overlay['bar']['mode'] == 'indeterminate':
                self.overlay['bar'].stop()
            if self.overlay['win']:
                self.overlay['win'].withdraw()
        except Exception:
            pass

    def _flush_overlay(self):
        try:
            frac = self._throttle_last['frac']
            msg = self._throttle_last['msg']
            self.update(frac, msg)
        finally:
            self._throttle_scheduled = False

    def schedule(self, frac, msg=None, delay=None):
        self._throttle_last['frac'] = frac
        self._throttle_last['msg'] = msg
        if delay is None:
            delay = self.debounce_ms
        if not self._throttle_scheduled:
            self._throttle_scheduled = True
            try:
                self.parent.after(delay, self._flush_overlay)
            except Exception:
                self._flush_overlay()

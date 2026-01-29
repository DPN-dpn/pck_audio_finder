import tkinter as tk
from tkinter import ttk
from ui.layout import build_layout
from ui import a_page, b_page
from util import logger

# Ensure bundled third-party tools are present (download if missing)
from util.lib_installer import ensure_libs


def run():
    # download required libs if missing (non-blocking could be added later)
    ensure_libs()

    root = tk.Tk()
    root.title("PCK Audio Finder")
    root.geometry("900x650")

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

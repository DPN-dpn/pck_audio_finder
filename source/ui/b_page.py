import tkinter as tk
from tkinter import ttk


def build(parent):
    """Temporary B page: show a centered placeholder label."""
    placeholder = ttk.Label(parent, text="B 탭 작업 영역", background="#f0f0f0", anchor="center")
    placeholder.pack(fill="both", expand=True)

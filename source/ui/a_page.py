import tkinter as tk
from tkinter import ttk, filedialog


def build(parent):
    top = ttk.Frame(parent)
    top.pack(fill="x", padx=6, pady=6)

    ttk.Label(top, text="경로:").pack(side="left")
    path_var = tk.StringVar()
    entry = ttk.Entry(top, textvariable=path_var)
    entry.pack(side="left", fill="x", expand=True, padx=(4, 4))

    def browse():
        p = filedialog.askdirectory()
        if p:
            path_var.set(p)

    ttk.Button(top, text="찾아보기", command=browse).pack(side="right")

    middle = ttk.Frame(parent)
    middle.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    left = ttk.Frame(middle, width=180)
    left.pack(side="left", fill="y")

    for i in range(6):
        btn = ttk.Button(left, text=f"버튼 {i+1}")
        btn.pack(fill="x", pady=4)

    right = ttk.Frame(middle)
    right.pack(side="left", fill="both", expand=True, padx=(6,0))

    placeholder = ttk.Label(right, text="A 탭의 작업 영역", background="#f0f0f0", anchor="center")
    placeholder.pack(fill="both", expand=True)

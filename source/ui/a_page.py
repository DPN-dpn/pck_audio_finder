import tkinter as tk
from tkinter import ttk
from .progress_overlay import ProgressOverlay
from .a_page_treeview import APageTree
from app.load_pck import load_pck as app_load_pck
from app.unpack import unpack_pck as app_unpack_pck
from app.convert_wav import convert_wav as app_convert_wav


def build(parent):
    # 레이아웃
    top = ttk.Frame(parent)
    top.pack(fill="x", padx=6, pady=6)

    middle = ttk.Frame(parent)
    middle.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    left = ttk.Frame(middle, width=180)
    left.pack(side="left", fill="y")

    right = ttk.Frame(middle)
    right.pack(side="left", fill="both", expand=True, padx=(6, 0))

    tree_frame = ttk.Frame(right)
    tree_frame.pack(fill="both", expand=True)

    # 트리뷰
    tree_manager = APageTree(tree_frame)

    # 프로그래스바 오버레이
    overlay = ProgressOverlay(parent)

    # 버튼1 PCK 로드
    btn1 = ttk.Button(
        left,
        text="PCK 읽어오기",
        command=lambda: app_load_pck(tree_manager, parent, overlay),
    )
    btn1.pack(fill="x", pady=4)

    # 버튼2 PCK 언팩
    btn = ttk.Button(
        left,
        text="PCK 언팩",
        command=lambda: app_unpack_pck(tree_manager, parent, overlay),
    )
    btn.pack(fill="x", pady=4)

    # 버튼3 WAV 변환
    btn = ttk.Button(
        left,
        text="WAV 변환",
        command=lambda: app_convert_wav(tree_manager, parent, overlay),
    )
    btn.pack(fill="x", pady=4)

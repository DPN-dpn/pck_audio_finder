import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from datetime import datetime
from util import config, logger
from app.pck_manage import load_pcks as manage_load_pcks, copy_selected_pcks_to_temp


def build(parent):
    top = ttk.Frame(parent)
    top.pack(fill="x", padx=6, pady=6)
    # 설정 파일이 존재하는지 확인하고 마지막 사용 경로를 로드합니다
    config.ensure_config()

    path_var = tk.StringVar()
    # 경로를 표시하되 사용자가 편집하지 못하도록 설정합니다
    entry = ttk.Entry(top, textvariable=path_var, state="disabled")
    entry.pack(side="left", fill="x", expand=True, padx=(4, 4))

    # 엔트리에 마지막으로 설정된 경로 또는 실행 디렉터리를 채웁니다
    last = config.get_str("ui", "last_path", fallback="")
    if last and Path(last).exists():
        path_var.set(last)
    else:
        path_var.set(str(Path.cwd()))

    def browse():
        # 저장된 마지막 경로가 유효하면 초기 디렉터리로 사용합니다
        last = config.get_str("ui", "last_path", fallback="")
        if last and Path(last).exists():
            initial = last
        else:
            # 마지막 경로가 없거나 유효하지 않으면 프로그램 실행 위치를 기본으로 사용합니다
            initial = str(Path.cwd())
        p = filedialog.askdirectory(initialdir=initial)
        if p:
            path_var.set(p)
            config.set_str("ui", "last_path", p)
            # 경로가 변경되면 이전에 불러온 데이터(트리)를 초기화합니다
            try:
                for iid in tree.get_children():
                    tree.delete(iid)
            except Exception:
                # tree가 아직 생성되지 않았거나 접근 불가한 경우 무시
                pass
            logger.log("UI", f"경로를 변경하여 로드된 데이터를 초기화했습니다: {p}")

    ttk.Button(top, text="찾아보기", command=browse).pack(side="right")

    middle = ttk.Frame(parent)
    middle.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    left = ttk.Frame(middle, width=180)
    left.pack(side="left", fill="y")

    # 우측 작업 영역: 트리뷰를 추가합니다
    right = ttk.Frame(middle)
    right.pack(side="left", fill="both", expand=True, padx=(6,0))

    tree_frame = ttk.Frame(right)
    tree_frame.pack(fill="both", expand=True)

    cols = ("name", "size", "modified")
    tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
    tree.heading("name", text="이름")
    tree.heading("size", text="크기")
    tree.heading("modified", text="수정일")
    tree.column("name", anchor="w")
    tree.column("size", width=100, anchor="e")
    tree.column("modified", width=160, anchor="center")

    vscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True, side="left")

    # load_pcks 동작은 앱 계층으로 이동했으므로 버튼은 그 함수를 호출합니다

    # Button 1: PCK 읽어오기
    btn1 = ttk.Button(left, text="PCK 읽어오기", command=lambda: manage_load_pcks(tree, path_var))
    btn1.pack(fill="x", pady=4)

    def extract_wav():
        dest, copied = copy_selected_pcks_to_temp(tree, path_var)
        if not copied:
            logger.log("UI", "복사할 PCK 파일이 없습니다")
            return
        # WAV 추출 동작을 비우고, 선택된 PCK 파일들을 temp/input_pck로 복제만 수행합니다
        logger.log("UI", f"PCK 파일을 복제했습니다: {dest}")
        for n in copied:
            logger.log("UI", f"  {n}")

    # Button 2: WAV 추출
    for i in range(2, 7):
        if i == 2:
            btn = ttk.Button(left, text="WAV 추출", command=extract_wav)
        else:
            btn = ttk.Button(left, text=f"버튼 {i}")
        btn.pack(fill="x", pady=4)

    # (기존 작업 영역 트리뷰로 대체되어 자리표시 라벨는 제거됨)

import tkinter as tk
from tkinter import ttk
from util import config as _config


def build_layout(root):
    _config.ensure_config()
    saved_log_h = _config.get_int("ui", "log_height", fallback=120)

    paned = ttk.PanedWindow(root, orient=tk.VERTICAL)
    paned.pack(fill="both", expand=True, padx=6, pady=6)

    # 상단: 탭 전환 버튼과 탭 컨테이너
    top_pane = ttk.Frame(paned)
    paned.add(top_pane, weight=1)

    # 탭 전환용 버튼 프레임
    switch_frame = ttk.Frame(top_pane)
    switch_frame.pack(fill="x")

    # 탭 컨테이너: 두 개의 프레임을 겹쳐 놓고 필요시 올립니다
    container = ttk.Frame(top_pane)
    container.pack(fill="both", expand=True)

    tab_a = ttk.Frame(container)
    tab_b = ttk.Frame(container)

    for f in (tab_a, tab_b):
        f.place(relx=0, rely=0, relwidth=1, relheight=1)

    # 탭 전환 버튼 (클릭 시 외부의 `show` 함수에 필요한 위젯 전달)
    btn_a = tk.Button(
        switch_frame,
        text="pck 맵핑",
        command=lambda: show("A", tab_a, tab_b, btn_a, btn_b),
    )
    btn_b = tk.Button(
        switch_frame,
        text="wav 검색",
        command=lambda: show("B", tab_a, tab_b, btn_a, btn_b),
    )

    btn_a.pack(side="left", fill="x", expand=True)
    btn_b.pack(side="left", fill="x", expand=True)

    # 기본 선택: A 탭
    btn_a.config(relief="sunken")
    tab_a.lift()

    # 하단: 로그 출력용 Text 위젯
    bottom_pane = ttk.Frame(paned)
    paned.add(bottom_pane, weight=0)
    try:
        paned.paneconfigure(bottom_pane, minsize=40)
    except Exception:
        pass

    log = tk.Text(bottom_pane)
    log.pack(fill="both", expand=True)

    # 초기 기하 정보가 준비되면 저장된 로그 높이에 맞춰 sash 위치를 복원
    root.after(40, lambda: _attempt_set_sash(8, paned, root, saved_log_h))

    # sash 드래그 해제 시 로그 높이를 설정에 저장
    paned.bind("<ButtonRelease-1>", lambda e: _on_release(e, paned, root))

    return tab_a, tab_b, log


def _on_release(event, paned, root):
    # sash 이동 완료 시 현재 로그 높이를 설정으로 저장
    try:
        toppos = paned.sashpos(0)
        cur_total = root.winfo_height()
        log_h = max(0, cur_total - toppos)
        _config.set_int("ui", "log_height", int(log_h))
    except Exception:
        pass


def _attempt_set_sash(retries, paned, root, saved_log_h):
    # 초기 윈도우 크기가 안정화될 때까지 재시도하며 sash 위치를 설정
    try:
        paned.update_idletasks()
        paned_h = paned.winfo_height()
        if paned_h <= 1 and retries > 0:
            root.after(
                40, lambda: _attempt_set_sash(retries - 1, paned, root, saved_log_h)
            )
            return
        if paned_h <= 1:
            paned_h = int(root.winfo_screenheight() * 0.6)
        top_h = max(0, int(paned_h) - int(saved_log_h))
        paned.sashpos(0, top_h)
    except Exception:
        pass


def show(tab_name, tab_a, tab_b, btn_a, btn_b):
    # 탭 전환: 선택 탭을 최상위로 올리고 버튼 스타일로 선택 표시
    if tab_name == "A":
        tab_a.lift()
        btn_a.config(relief="sunken")
        btn_b.config(relief="raised")
    else:
        tab_b.lift()
        btn_b.config(relief="sunken")
        btn_a.config(relief="raised")

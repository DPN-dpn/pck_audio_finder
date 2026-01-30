import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from datetime import datetime
from util import logger
from app.pck_manage import load_pcks as manage_load_pcks, unpack_copied_pcks_to_data
from .progress_overlay import ProgressOverlay
import threading


def build(parent):
    top = ttk.Frame(parent)
    top.pack(fill="x", padx=6, pady=6)
    # 경로 설정 UI 제거: 프로그램 내부의 input_pck 고정 경로 사용
    # 프로그램 시작 시 input_pck 폴더가 없으면 생성
    try:
        workspace_root = Path(__file__).resolve().parents[2]
        startup_input = workspace_root / 'input_pck'
        startup_input.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    middle = ttk.Frame(parent)
    middle.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    left = ttk.Frame(middle, width=180)
    left.pack(side="left", fill="y")

    # 우측 작업 영역: 트리뷰를 추가합니다
    right = ttk.Frame(middle)
    right.pack(side="left", fill="both", expand=True, padx=(6,0))

    tree_frame = ttk.Frame(right)
    tree_frame.pack(fill="both", expand=True)

    cols = ("size", "modified")
    # show tree column (#0) so expand/collapse icons appear, and keep headings for other cols
    tree = ttk.Treeview(tree_frame, columns=cols, show="tree headings")
    tree.heading("#0", text="이름")
    tree.heading("size", text="크기")
    tree.heading("modified", text="수정일")
    tree.column("#0", anchor="w", width=240)
    tree.column("size", width=100, anchor="e")
    tree.column("modified", width=160, anchor="center")

    vscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True, side="left")
    # load_pcks 동작은 앱 계층으로 이동했으므로 버튼은 그 함수를 호출합니다

    # use ProgressOverlay module for UI overlay
    overlay = ProgressOverlay(parent)

    # Button 1: PCK 읽어오기
    def load_and_populate():
        # show determinate overlay while scanning
        overlay.show("PCK 목록을 불러오는 중...", maximum=1.0, indeterminate=False)

        def worker():
            entries = []

            def _sanitize_msg(msg):
                if not msg:
                    return None
                try:
                    # known prefixes
                    prefixes = ["로딩 PCK", "처리 시작:", "이미 언팩됨:", "언팩 완료:", "JSON 생성:", "파일 없음:", "언팩 실패:"]
                    for p in prefixes:
                        if p in msg:
                            return msg
                    # fallback shorten
                    return msg if len(msg) <= 60 else msg[:57] + '...'
                except Exception:
                    return None

            def cb(frac, message=None):
                try:
                    # only show load-progress messages (e.g. '로딩 PCK') in overlay
                    msg = _sanitize_msg(message)
                    show_keys = ("로딩 PCK",)
                    display = None
                    try:
                        if message and any(k in message for k in show_keys):
                            display = msg
                    except Exception:
                        display = msg
                    parent.after(1, lambda: overlay.schedule(frac, display))
                except Exception:
                    pass

            try:
                entries = manage_load_pcks(progress_cb=cb)
            except Exception:
                entries = []

            def on_done():
                # clear existing
                try:
                    for iid in tree.get_children():
                        tree.delete(iid)
                except Exception:
                    pass
                for e in entries:
                    try:
                        tree.insert("", "end", text=e['name'], values=(str(e['size']), e['modified']))
                    except Exception:
                        pass
                overlay.hide()

            parent.after(50, on_done)

        threading.Thread(target=worker, daemon=True).start()

    btn1 = ttk.Button(left, text="PCK 읽어오기", command=load_and_populate)
    btn1.pack(fill="x", pady=4)

    def extract_wav():
        # gather selection (PCK names)
        items = tree.selection()
        if not items:
            items = tree.get_children()
        names = []
        for iid in items:
            try:
                it = tree.item(iid)
                name = it.get('text') or (it.get('values') or [None])[0]
                if name:
                    names.append(name)
            except Exception:
                continue

        if not names:
            logger.log("UI", "선택된 PCK 파일이 없습니다")
            return

        # 고정 입력 폴더: 프로젝트의 input_pck
        workspace_root = Path(__file__).resolve().parents[2]
        input_dir = workspace_root / 'input_pck'

        total = len(names)
        overlay.show("WAV 추출 중...", maximum=1.0, indeterminate=False)

        def update_tree_for_name(name):
            try:
                data_root = workspace_root / 'data'
                # find tree item whose text matches the pck filename
                target_iid = None
                for iid in tree.get_children():
                    try:
                        it = tree.item(iid)
                        if it.get('text') == name:
                            target_iid = iid
                            break
                    except Exception:
                        continue
                if not target_iid:
                    return

                # remove existing children
                try:
                    for child in tree.get_children(target_iid):
                        tree.delete(child)
                except Exception:
                    pass

                unpack_dir = data_root / (Path(name).stem + '_unpacked')
                if not unpack_dir.exists():
                    return

                # add root files
                for p in sorted(unpack_dir.iterdir()):
                    if p.is_file():
                        try:
                            tree.insert(target_iid, 'end', text=p.name, values=(str(p.stat().st_size), datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')))
                        except Exception:
                            pass

                # add bnk folders
                for child in sorted(unpack_dir.iterdir()):
                    if child.is_dir() and child.name.lower().endswith('_bnk'):
                        try:
                            folder_iid = tree.insert(target_iid, 'end', text=child.name + '/', values=('', ''))
                            for file in sorted(child.rglob('*')):
                                if file.is_file():
                                    try:
                                        rel = file.relative_to(child)
                                        tree.insert(folder_iid, 'end', text=str(rel), values=(str(file.stat().st_size), datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')))
                                    except Exception:
                                        pass
                        except Exception:
                            pass
            except Exception:
                pass

        def progress_cb(frac, message=None):
            # sanitize messages and debounce updates
            def _sanitize(msg):
                if not msg:
                    return None
                try:
                    # handle common patterns and reduce paths to names
                    if '파일 작성:' in msg:
                        right = msg.split('파일 작성:', 1)[1].strip()
                        name = Path(right).name
                        return f'파일 작성: {name}'
                    if 'BNK 처리:' in msg:
                        right = msg.split('BNK 처리:', 1)[1].strip()
                        name = Path(right).name
                        return f'BNK 처리: {name}'
                    if 'BNK에 데이터 없음:' in msg:
                        right = msg.split('BNK에 데이터 없음:', 1)[1].strip()
                        name = Path(right).name
                        return f'BNK 없음: {name}'
                    # keep pck_manage keywords intact
                    for kw in ('JSON 생성', '언팩 완료', '이미 언팩됨', '언팩 내부 완료', '언팩 실패', '파일 없음'):
                        if kw in msg:
                            return msg
                    return msg if len(msg) <= 60 else msg[:57] + '...'
                except Exception:
                    return None

            def ui_update():
                try:
                    m = _sanitize(message)
                    # prefer showing in-progress messages only
                    in_progress_keys = ("언팩 중", "파일 작성", "BNK 처리", "처리 시작", "구조 수집", "JSON 작성")
                    display = None
                    if message and any(k in message for k in in_progress_keys):
                        display = m
                    overlay.schedule(frac, display)
                    # when a file is completed, update tree
                    if message:
                        for kw in ("JSON 생성", "언팩 완료", "이미 언팩됨", "언팩 내부 완료", "트리 반영"):
                            if kw in message:
                                parts = message.split(':', 1)
                                if len(parts) > 1:
                                    nm = parts[1].strip()
                                    update_tree_for_name(nm)
                                break
                except Exception:
                    pass

            try:
                parent.after(1, ui_update)
            except Exception:
                pass

        def worker():
            try:
                unpack_copied_pcks_to_data(str(input_dir), names, progress_cb=progress_cb)
            except Exception as e:
                logger.log("UI", f"언팩 처리 중 오류(내부): {e}")

            # ensure overlay hidden when finished
            parent.after(100, overlay.hide)

        threading.Thread(target=worker, daemon=True).start()

    for i in range(2, 7):
        if i == 2:
            btn = ttk.Button(left, text="WAV 추출", command=extract_wav)
        else:
            btn = ttk.Button(left, text=f"버튼 {i}")
        btn.pack(fill="x", pady=4)

    # (기존 작업 영역 트리뷰로 대체되어 자리표시 라벨는 제거됨)

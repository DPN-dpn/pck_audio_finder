import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from datetime import datetime
from util import logger
from app.pck_manage import load_pcks as manage_load_pcks, unpack_copied_pcks_to_data


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

    # Button 1: PCK 읽어오기
    def load_and_populate():
        entries = manage_load_pcks()
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

        try:
            jsons = unpack_copied_pcks_to_data(str(input_dir), names)
            if not jsons:
                logger.log("UI", "언팩 또는 JSON 생성된 항목이 없습니다")
                return
            logger.log("UI", "언팩 및 JSON 생성 완료:")
            for j in jsons:
                logger.log("UI", f"  {j}")

            # update tree: attach unpacked children under each PCK item
            workspace_root = Path(__file__).resolve().parents[2]
            data_root = workspace_root / 'data'
            for name in names:
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
                    continue

                # remove existing children
                try:
                    for child in tree.get_children(target_iid):
                        tree.delete(child)
                except Exception:
                    pass

                unpack_dir = data_root / (Path(name).stem + '_unpacked')
                if not unpack_dir.exists():
                    continue

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
        except Exception as e:
            logger.log("UI", f"언팩 처리 중 오류: {e}")

    for i in range(2, 7):
        if i == 2:
            btn = ttk.Button(left, text="WAV 추출", command=extract_wav)
        else:
            btn = ttk.Button(left, text=f"버튼 {i}")
        btn.pack(fill="x", pady=4)

    # (기존 작업 영역 트리뷰로 대체되어 자리표시 라벨는 제거됨)

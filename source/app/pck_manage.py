from pathlib import Path
from datetime import datetime
from util import logger, config
import shutil


"""앱 레벨의 PCK 관리기능 — 단순화 버전.

이 모듈은 UI에서 호출되는 `load_pcks(tree, path_var)` 하나를 제공하며,
경로 조회 및 `.pck` 검색 로직을 내부에서 처리합니다.
"""


def load_pcks(tree, path_var) -> None:
    """UI에서 사용하는 함수.

    - `tree`: tkinter Treeview 인스턴스
    - `path_var`: tkinter StringVar 인스턴스 (경로 표시기)

    이 함수는 설정에 저장된 마지막 경로(`ui.last_path`)를 우선 사용하고,
    없으면 현재 작업 디렉터리를 기본으로 삼습니다. 그런 다음 해당 폴더의
    `.pck` 파일을 찾아 `tree`에 표시합니다.
    """
    # 설정에서 경로 결정
    p = config.get_str("ui", "last_path", fallback="")
    if p and Path(p).exists():
        folder = Path(p)
    else:
        folder = Path.cwd()

    # .pck 파일 목록 생성
    try:
        pck_files = [x for x in folder.iterdir() if x.is_file() and x.suffix.lower() == ".pck"]
    except Exception:
        pck_files = []

    path_var.set(str(folder))

    # 트리 초기화
    try:
        for iid in tree.get_children():
            tree.delete(iid)
    except Exception:
        pass

    if not pck_files:
        logger.log("PCK", f"{folder}에서 .pck 파일을 찾을 수 없습니다")
        return

    logger.log("PCK", f"{folder}에서 {len(pck_files)}개의 .pck 파일을 찾았습니다:")
    for f in pck_files:
        logger.log("PCK", f"  {f.name}")
        try:
            st = f.stat()
            size = st.st_size
            modified = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            size = 0
            modified = ""
        try:
            tree.insert("", "end", values=(f.name, str(size), modified))
        except Exception:
            # 트리 삽입 실패해도 계속
            pass


def copy_selected_pcks_to_temp(tree, path_var) -> tuple:
    """선택된(또는 트리에 로드된) PCK 파일들을 시스템 임시 폴더 아래
    `pck_audio_finder_temp/input_pck`로 복사합니다. 기존 내용을 삭제하고 새로 복사합니다.

    반환: (input_pck_path, [filenames])
    """
    try:
        src_folder = Path(path_var.get()) if path_var and path_var.get() else Path.cwd()
    except Exception:
        src_folder = Path.cwd()

    # use project's temp folder (workspace_root/temp/input_pck)
    try:
        workspace_root = Path(__file__).resolve().parents[2]
    except Exception:
        workspace_root = Path.cwd()
    temp_root = workspace_root / 'temp'
    input_pck_dir = temp_root / 'input_pck'
    # remove previous input_pck contents only
    if input_pck_dir.exists():
        try:
            shutil.rmtree(input_pck_dir)
        except Exception:
            pass
    input_pck_dir.mkdir(parents=True, exist_ok=True)

    items = tree.selection()
    if not items:
        items = tree.get_children()

    copied = []
    for iid in items:
        try:
            vals = tree.item(iid).get('values') or ()
            name = vals[0] if vals else None
            if not name:
                continue
            src = src_folder / name
            if src.exists() and src.is_file():
                shutil.copy2(src, input_pck_dir / src.name)
                copied.append(src.name)
            else:
                logger.log("PCK", f"파일이 존재하지 않음: {src}")
        except Exception as e:
            logger.log("PCK", f"복사 실패: {e}")

    logger.log("PCK", f"{input_pck_dir}으로 {len(copied)}개 파일을 복사했습니다")
    return (str(input_pck_dir), copied)


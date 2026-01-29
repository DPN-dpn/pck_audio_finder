from pathlib import Path
from datetime import datetime
from util import logger, config


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


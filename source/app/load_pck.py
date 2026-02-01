import threading
from typing import Optional, List, Dict, Any
from pathlib import Path
from util import logger
from model.storage import storage


def load_pck(tree_manager, parent, overlay: Optional[object] = None) -> None:
    """`input_pck` 폴더에서 .pck 파일을 스캔하여 `storage`에 저장하고
    트리뷰에 반영합니다.

    변경사항:
    - 예외를 과도하게 숨기지 않고, 실패는 로그로 남김
    - 동기화는 storage.set_pck_list(entries)를 기본으로 사용
    - UI 관련 작업은 항상 메인 스레드에서 수행하도록 `parent.after` 사용
    """

    # 오버레이 표시 (있으면)
    if overlay is not None:
        try:
            overlay.show("PCK 불러오는 중...", maximum=1.0, indeterminate=False)
        except Exception as e:
            logger.log("PCK", f"overlay.show 실패: {e}")

    def worker():
        # 작업 루트 및 input_pck 폴더 결정
        workspace_root = Path(__file__).resolve().parents[2]
        folder_path = workspace_root / "input_pck"

        # .pck 파일 목록 수집
        pck_files: List[Path] = []
        try:
            if folder_path.exists() and folder_path.is_dir():
                pck_files = [
                    p
                    for p in folder_path.iterdir()
                    if p.is_file() and p.suffix.lower() == ".pck"
                ]
        except Exception as e:
            logger.log("PCK", f"input_pck 스캔 실패: {e}")

        # 항목 생성: name + path(가능하면 워크스페이스 상대경로)
        entries: List[Dict[str, Any]] = []
        if not pck_files:
            logger.log("PCK", f"{folder_path}에서 .pck 파일을 찾을 수 없습니다")
        else:
            logger.log(
                "PCK", f"{folder_path}에서 {len(pck_files)}개의 .pck 파일을 찾았습니다"
            )
            for f in pck_files:
                rel = f.relative_to(workspace_root)
                path_str = rel.as_posix()
                entries.append({"name": f.name, "path": path_str})

        # storage에 저장
        try:
            storage.set_pck_list(entries)
        except Exception as e:
            logger.log("PCK", f"storage.set_pck_list 실패: {e}")

        # UI 갱신 예약
        def on_done():
            try:
                # tree_manager API로 삽입(있으면)
                try:
                    pck_items = storage.get_pck_list()
                except Exception:
                    pck_items = entries

                if hasattr(tree_manager, "insert_pcks") and callable(
                    tree_manager.insert_pcks
                ):
                    tree_manager.insert_pcks(pck_items)
                elif (
                    hasattr(tree_manager, "a_page_treeview")
                    and tree_manager.a_page_treeview is not None
                ):
                    # fallback: 직접 a_page_treeview에 항목을 추가
                    for e in pck_items:
                        try:
                            tree_manager.a_page_treeview.insert(
                                "", "end", text=e.get("name"), values=("", "")
                            )
                        except Exception as ex:
                            logger.log("PCK", f"트리 직접 삽입 실패: {ex}")

                logger.log(
                    "PCK", f"PCK 목록 {len(pck_items)}개를 트리뷰에 추가했습니다"
                )

            finally:
                # 오버레이 숨김 및 storage 저장
                if overlay is not None:
                    try:
                        overlay.hide()
                    except Exception as e:
                        logger.log("PCK", f"overlay.hide 실패: {e}")
                try:
                    storage.save()
                except Exception as e:
                    logger.log("PCK", f"storage.save 실패: {e}")

        # UI 스레드에서 완료 처리
        try:
            parent.after(50, on_done)
        except Exception:
            on_done()

    threading.Thread(target=worker, daemon=True).start()

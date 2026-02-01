import threading
from util import logger


def convert_wav(tree_manager, parent, overlay: object = None) -> None:
    """WEM 변환 진입점.

    현재는 오버레이를 표시하고 백그라운드 스레드에서 작업을 수행한 뒤
    오버레이를 숨기는 기본 동작만 구현합니다. 실제 변환/청크 분할 로직은
    이후에 추가하세요.
    """
    # 오버레이는 UI 스레드에서 표시해야 안전합니다.
    try:
        if overlay is not None:
            try:
                parent.after(0, lambda: overlay.show("WEM 목록 생성 중...", maximum=1.0, indeterminate=True))
            except Exception:
                overlay.show("WEM 목록 생성 중...", maximum=1.0, indeterminate=True)
    except Exception as e:
        logger.log("CONVERT", f"오버레이 표시 실패: {e}")

    def _worker():
        # TODO: 실제 WEM 청크 구분/변환 작업을 이곳에 구현
        try:
            # placeholder 작업(빠르게 종료)
            pass
        finally:
            # 작업 완료 후 오버레이 숨기기(메인 스레드에서)
            try:
                if overlay is not None:
                    parent.after(1, lambda: overlay.hide())
            except Exception:
                try:
                    if overlay is not None:
                        overlay.hide()
                except Exception as e:
                    logger.log("CONVERT", f"오버레이 숨김 실패: {e}")

    threading.Thread(target=_worker, daemon=True).start()

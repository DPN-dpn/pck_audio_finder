import tkinter as tk
from tkinter import ttk
from ui.layout import build_layout
from ui import a_page, b_page
from util import logger
from util import config as _config

from model import set_global_model, Storage  # initialize model from app startup
from pathlib import Path

# 간단한 실행 흐름:
# 1) 필요한 외부 도구 확인/설치
# 2) 작업 디렉토리 생성
# 3) 윈도우 초기화 및 이전 크기 복원
# 4) 크기 변경시 설정 저장(디바운스)
# 5) 레이아웃 구성, 로거 연결, 페이지 빌드


def run():
    # 필요한 외부 도구 설치/확인
    # 런처(launch.bat)에서 라이브러리 설치를 처리하도록 변경됨

    # 작업 폴더가 없으면 생성
    try:
        workspace_root = Path(__file__).resolve().parents[1]
        (workspace_root / "input_pck").mkdir(parents=True, exist_ok=True)
        (workspace_root / "data").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # 메인 윈도우 생성
    root = tk.Tk()
    root.title("PCK Audio Finder")

    # 이전에 저장된 창 크기 복원 (없으면 기본값)
    try:
        _config.ensure_config()
        saved_w = _config.get_int("ui", "window_width", fallback=0)
        saved_h = _config.get_int("ui", "window_height", fallback=0)
        if saved_w and saved_h:
            root.geometry(f"{saved_w}x{saved_h}")
        else:
            root.geometry("900x650")
    except Exception:
        root.geometry("900x650")

    try:
        root.bind("<Configure>", _schedule_save)
        root.protocol("WM_DELETE_WINDOW", _on_close)
    except Exception:
        pass

    # 레이아웃 구성, 로거 연결, 페이지 초기화
    tab_a, tab_b, log = build_layout(root)
    logger.attach(log)
    # 전역 모델 초기화: 기능 계층에서 모델을 생성
    try:
        set_global_model(Storage())
    except Exception:
        pass
    a_page.build(tab_a)
    b_page.build(tab_b)
    root.mainloop()

    def _on_close():
        try:
            # 종료 시 마지막 크기 저장 후 윈도우 파괴
            w = root.winfo_width()
            h = root.winfo_height()
            _config.set_int("ui", "window_width", int(w))
            _config.set_int("ui", "window_height", int(h))
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    def _schedule_save(e=None):
        # 창 크기 변경을 디바운스하여 설정에 저장
        try:
            if getattr(root, "_save_after_id", None):
                root.after_cancel(root._save_after_id)

            def _do_save():
                try:
                    w = root.winfo_width()
                    h = root.winfo_height()
                    _config.set_int("ui", "window_width", int(w))
                    _config.set_int("ui", "window_height", int(h))
                except Exception:
                    pass

            root._save_after_id = root.after(500, _do_save)
        except Exception:
            pass


if __name__ == "__main__":
    run()

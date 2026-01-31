import tkinter as tk
from tkinter import ttk
from typing import Optional

from util import logger


class ProgressOverlay:
    """간단한 진행 오버레이 위젯.

    - `show`: 오버레이 생성 및 표시
    - `update`: 진행률/메시지 업데이트
    - `hide`: 오버레이 숨김
    - `schedule`: 빈번한 업데이트를 디바운스하여 메인 스레드 부하를 낮춤
    """

    def __init__(self, parent: tk.Widget, debounce_ms: int = 100):
        self.parent = parent
        self.debounce_ms = int(debounce_ms)
        self.overlay = {"win": None, "bar": None, "label": None, "sub_label": None}
        self._throttle_scheduled = False
        self._throttle_last = {"frac": 0.0, "msg": None, "submsg": None}

        # 설명:
        # - `overlay`는 실제 오버레이 위젯들을 참조하는 딕셔너리입니다.
        # - `_throttle_last`와 `_throttle_scheduled`은 빈번한 업데이트를
        #   디바운스(schedule)하기 위한 내부 상태입니다.

    def _create_overlay(self) -> None:
        root = self.parent.winfo_toplevel()
        ow = tk.Toplevel(root)
        ow.overrideredirect(True)
        try:
            ow.transient(root)
        except Exception:
            # 일부 플랫폼에서 지원되지 않을 수 있음
            pass

        # 위치/크기 초기화 — 실패 시 로그만 남기고 진행
        try:
            x = root.winfo_rootx()
            y = root.winfo_rooty()
            w = root.winfo_width()
            h = root.winfo_height()
            ow.geometry(f"{w}x{h}+{x}+{y}")
        except Exception as e:
            logger.log("UI", f"overlay geometry 설정 실패: {e}")

        # 오버레이가 최상위에 보이도록 설정
        ow.attributes("-topmost", True)
        try:
            ow.wm_attributes("-alpha", 0.6)
        except Exception:
            # 일부 환경에서는 투명도 설정이 동작하지 않음
            pass

        frm = ttk.Frame(ow)
        frm.place(relx=0.5, rely=0.5, anchor="center")
        lbl = ttk.Label(frm, text="작업 중...")
        lbl.pack(padx=8, pady=(0, 2))
        sub_lbl = ttk.Label(frm, text="", foreground="#444")
        sub_lbl.pack(padx=8, pady=(0, 6))
        pb = ttk.Progressbar(frm, orient="horizontal", length=300, mode="determinate")
        pb.pack(padx=8, pady=6)

        self.overlay["win"] = ow
        self.overlay["bar"] = pb
        self.overlay["label"] = lbl
        self.overlay["sub_label"] = sub_lbl

        # 루트 윈도우가 이동/리사이즈될 때 오버레이 위치를 업데이트
        def _on_root_config(event=None):
            if not self.overlay.get("win"):
                return
            try:
                st = root.state()
                if st == "iconic":
                    self.overlay["win"].withdraw()
                    return
            except Exception:
                # 상태 조회 실패는 무시
                pass
            try:
                x = root.winfo_rootx()
                y = root.winfo_rooty()
                w = root.winfo_width()
                h = root.winfo_height()
                self.overlay["win"].geometry(f"{w}x{h}+{x}+{y}")
            except Exception as e:
                logger.log("UI", f"overlay 재배치 실패: {e}")

        # Configure 이벤트에 바인드하여 루트 윈도우의 이동/크기변경을
        # 추적합니다. 이렇게 하면 오버레이가 항상 루트 창을 덮도록 유지됩니다.
        root.bind("<Configure>", _on_root_config)

    def show(self, message: str = "작업 중...", submessage: Optional[str] = None, maximum: Optional[float] = None, indeterminate: bool = False) -> None:
        """오버레이를 생성(필요 시)하고 표시합니다."""
        if self.overlay["win"] is None:
            self._create_overlay()
        # 기본 텍스트는 항상 덮어씀
        self.overlay["label"].config(text=message)
        if submessage is None:
            self.overlay["sub_label"].config(text="")
        else:
            self.overlay["sub_label"].config(text=submessage)

        if indeterminate:
            self.overlay["bar"].config(mode="indeterminate")
            self.overlay["bar"].start(10)
        else:
            self.overlay["bar"].config(mode="determinate")
            if maximum is not None:
                try:
                    self.overlay["bar"]["maximum"] = maximum
                except Exception:
                    logger.log("UI", "progressbar maximum 설정 실패")
            self.overlay["bar"]["value"] = 0

        self.overlay["win"].deiconify()
        self.overlay["win"].lift()

        # 주의: `show`는 메인 스레드에서 호출되어야 안전합니다. 백그라운드
        # 스레드에서 호출할 경우 반드시 `parent.after(...)`로 래핑하세요.

    def update(self, value: float, message: Optional[str] = None, submessage: Optional[str] = None) -> None:
        """진행률과 메시지를 즉시 업데이트합니다."""
        if self.overlay.get("bar") is not None:
            try:
                self.overlay["bar"]["value"] = value
            except Exception as e:
                logger.log("UI", f"progressbar 업데이트 실패: {e}")

        if message is not None:
            self.overlay["label"].config(text=message)
            # 메시지가 변경되면 submessage가 없을 경우 서브 텍스트를 비움
            if submessage is None:
                self.overlay["sub_label"].config(text="")
            else:
                self.overlay["sub_label"].config(text=submessage)
        elif submessage is not None:
            self.overlay["sub_label"].config(text=submessage)

        # update 역시 메인 스레드에서 안전하게 호출되어야 합니다.
        # 다른 스레드에서 값 반영이 필요하면 `parent.after`를 사용하세요.

    def hide(self) -> None:
        """오버레이를 숨깁니다. indeterminate 모드는 중지합니다."""
        if self.overlay.get("bar") is not None:
            try:
                if self.overlay["bar"]["mode"] == "indeterminate":
                    self.overlay["bar"].stop()
            except Exception:
                pass
        if self.overlay.get("win") is not None:
            self.overlay["win"].withdraw()

        # hide도 메인 스레드에서 호출하세요. 스레드 안전을 위해 필요하면
        # `parent.after(0, overlay.hide)` 형태로 호출하도록 하세요.

    def _flush_overlay(self) -> None:
        frac = self._throttle_last["frac"]
        msg = self._throttle_last["msg"]
        sub = self._throttle_last.get("submsg")
        self.update(frac, msg, sub)
        self._throttle_scheduled = False

        # _flush_overlay는 schedule로 예약된 시점에 메인 스레드에서 실행됩니다.
        # 내부적으로 update를 호출하므로 UI 스레드에서 안전하게 동작합니다.

    def schedule(self, frac: float, msg: Optional[str] = None, submsg: Optional[str] = None, delay: Optional[int] = None) -> None:
        """자주 호출되는 업데이트를 디바운스하여 메인 스레드 부하를 줄입니다."""
        self._throttle_last["frac"] = frac
        self._throttle_last["msg"] = msg
        self._throttle_last["submsg"] = submsg
        if delay is None:
            delay = self.debounce_ms
        if not self._throttle_scheduled:
            self._throttle_scheduled = True
            try:
                self.parent.after(delay, self._flush_overlay)
            except Exception:
                # after 호출 불가 시 즉시 flush
                self._flush_overlay()

        # 사용법 예:
        # - 백그라운드 작업에서 빈번한 진행률 업데이트가 발생할 때
        #   `overlay.schedule(frac, '처리중', '파일명')` 을 호출하면 실제 UI
        #   업데이트는 디바운스되어 `delay` 간격으로만 적용됩니다.

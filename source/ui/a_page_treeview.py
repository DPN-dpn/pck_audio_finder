import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any, Optional
from util import config as _config
from util import logger
from model.storage import Storage

# 전역 storage 싱글톤(있다면) 가져오기
try:
    from model.storage import storage as _global_storage
except Exception:
    _global_storage = None


class APageTree:
    """A 탭의 TreeView를 관리하는 경량 클래스.

    이 클래스는 UI 위젯을 생성하고, 저장소(`Storage`)의 PCK 목록 변경을
    리스닝하여 트리 항목을 갱신합니다. 설계는 단순합니다:

    - 저장소 -> UI : 이벤트(리스너)로 동기화
    - UI -> 저장소 : 직접 쓰지 않음 (피드백 루프 회피)
    - 에러는 숨기지 않고 `util.logger.log`에 기록

    책임:
    - 트리(이름/분류/자막) 생성 및 레이아웃
    - 컬럼 너비 복원/저장
    - 저장소에서 전달된 PCK 목록을 트리에 반영
    - 특정 PCK에 대한 상세 listing(예: wem, bnk)을 하위 노드로 표시
    """

    def __init__(self, parent: tk.Widget, model: Optional[Storage] = None):
        """위젯을 초기화하고, 가능한 경우 저장소 리스너를 등록합니다.

        인자:
        - parent: 트리를 포함할 부모 위젯(tk.Frame 등)
        - model: 테스트/DI 용으로 주입 가능한 `Storage` 인스턴스. 주입되지 않으면
                 모듈 수준의 전역 `storage` 싱글톤(`_global_storage`)을 사용합니다.
        """
        self.parent = parent
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="both", expand=True)

        # 주입된 모델이 없으면 전역 싱글톤 사용
        self.model = model or _global_storage

        # --- TreeView 생성 -------------------------------------------------
        # 컬럼: 루트 텍스트('#0')는 파일/아카이브 이름, 추가 컬럼은 필요시 사용
        cols = ("category", "subtitle")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="tree headings")
        self.tree.heading("#0", text="이름")
        self.tree.heading("category", text="분류")
        self.tree.heading("subtitle", text="자막")

        # 컬럼 너비: 이전에 저장된 값이 있으면 불러오고, 없으면 기본값 사용
        try:
            name_w = _config.get_int("ui", "col_name_width", fallback=184)
            cat_w = _config.get_int("ui", "col_category_width", fallback=70)
            sub_w = _config.get_int("ui", "col_subtitle_width", fallback=120)
        except Exception as e:
            # 설정 파일이 손상되었거나 값 읽기에 실패하면 로그만 남기고 기본값 사용
            logger.log("UI", f"컬럼 너비 설정 읽기 실패: {e}")
            name_w, cat_w, sub_w = 184, 70, 120

        # 컬럼 너비 적용
        self.tree.column("#0", anchor="w", width=name_w)
        self.tree.column("category", width=cat_w, anchor="center")
        self.tree.column("subtitle", width=sub_w, anchor="w")

        # 수직 스크롤바 연결 및 배치
        vscroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, side="left")

        # --- 레이아웃 기반 subtitle 컬럼 너비 자동 조정 -------------------------
        # 프레임이 그려진 뒤 가용 너비를 기준으로 subtitle 컬럼을 확장합니다.
        def _adjust_subtitle_width(retries: int = 6):
            # 윈도우가 초기화 중일 때는 너비가 1 이하일 수 있으므로 재시도 로직 사용
            w = self.frame.winfo_width()
            if w <= 1 and retries > 0:
                self.parent.after(80, lambda: _adjust_subtitle_width(retries - 1))
                return
            avail = max(60, int(w) - int(name_w) - int(cat_w) - 8)
            self.tree.column("subtitle", width=avail)
            # 사용자 설정에 현재 너비를 저장하려고 시도하되 실패하면 로그만 남김
            try:
                _config.set_int("ui", "col_subtitle_width", int(avail))
            except Exception:
                logger.log("UI", "col_subtitle_width 저장 실패")

        self.parent.after(120, _adjust_subtitle_width)

        # --- 컬럼 너비 변경 감지 및 저장(폴링) -------------------------------
        # 사용자가 컬럼을 드래그하여 크기를 바꿀 수 있으므로 주기적으로 검사하여
        # 변경이 있으면 설정에 저장합니다.
        last_widths = {
            "#0": self.tree.column("#0", option="width"),
            "category": self.tree.column("category", option="width"),
            "subtitle": self.tree.column("subtitle", option="width"),
        }

        def _poll_widths():
            try:
                cur_name = self.tree.column("#0", option="width")
                cur_cat = self.tree.column("category", option="width")
                cur_sub = self.tree.column("subtitle", option="width")
                if cur_name != last_widths["#0"]:
                    _config.set_int("ui", "col_name_width", int(cur_name))
                    last_widths["#0"] = cur_name
                if cur_cat != last_widths["category"]:
                    _config.set_int("ui", "col_category_width", int(cur_cat))
                    last_widths["category"] = cur_cat
                if cur_sub != last_widths["subtitle"]:
                    _config.set_int("ui", "col_subtitle_width", int(cur_sub))
                    last_widths["subtitle"] = cur_sub
            except Exception as e:
                # 폴링 중에 발생한 예외는 로그로 남기고 다시 예약
                logger.log("UI", f"컬럼 너비 폴링 오류: {e}")
            finally:
                self.parent.after(1000, _poll_widths)

        self.parent.after(1000, _poll_widths)

        # --- 저장소가 있다면 리스너 등록 -------------------------------------
        # 저장소에서 PCK 목록이 변경되면 이 리스너를 통해 UI 트리를 갱신합니다.
        if self.model is not None and hasattr(self.model, "register_pck_list_listener"):

            def _sync_and_apply(items: List[Dict[str, Any]]):
                # 우선순위: storage.unpack_results가 있으면 그 키들만 트리에 적용
                # (pck_list는 무시). unpack_results가 비어있으면 pck_list를 적용.
                try:
                    ur = getattr(self.model, "unpack_results", None)
                except Exception:
                    ur = None

                if isinstance(ur, dict) and ur:
                    # unpack_results에 있는 항목들로 트리 초기화
                    entries = [{"name": k} for k in ur.keys()]
                    self.insert_pcks(entries)
                    for name, res in ur.items():
                        try:
                            if res:
                                self.apply_listing(name, res)
                        except Exception:
                            logger.log("UI", f"apply_listing 실패: {name}")
                    return

                # unpack_results가 없으면 pck_list를 사용
                if not isinstance(items, list):
                    return
                self.insert_pcks(items)
                # pck_list 항목 중 unpack_results가 별도 존재하는 경우만 상세 적용
                for e in items:
                    if not isinstance(e, dict):
                        continue
                    name = e.get("name")
                    if not name:
                        continue
                    try:
                        if hasattr(self.model, "get_unpack_result"):
                            res = self.model.get_unpack_result(name)
                            if res:
                                try:
                                    self.apply_listing(name, res)
                                except Exception:
                                    logger.log("UI", f"apply_listing 실패: {name}")
                    except Exception:
                        logger.log("UI", f"get_unpack_result 실패: {name}")

            def _on_pck_list(items: List[Dict[str, Any]]):
                # storage는 별도 스레드에서 변경 알림을 줄 수 있으므로
                # UI 갱신은 항상 메인 스레드에서 수행되도록 `after`로 예약합니다.
                self.parent.after(1, lambda it=items: _sync_and_apply(it))

            try:
                self.model.register_pck_list_listener(_on_pck_list)
            except Exception as e:
                logger.log("UI", f"storage 리스너 등록 실패: {e}")

            # 이미 로드된 목록이 있으면 즉시 동기화 및 unpack_results 적용
            try:
                current = self.model.get_pck_list()
                if current:
                    self.parent.after(1, lambda: _sync_and_apply(current))
            except Exception as e:
                logger.log("UI", f"storage 초기 목록 조회 실패: {e}")

            # 또한 storage에 이미 저장된 unpack_results가 있으면 초기화 시점에
            # 트리에 반영합니다. pck_list에 없는 항목이라도 루트로 추가합니다.
            try:
                ur = getattr(self.model, "unpack_results", None)
                if isinstance(ur, dict) and ur:

                    def _apply_all_unpack_results():
                        try:
                            # 현재 트리 루트 이름 목록
                            existing = [
                                self.tree.item(i)["text"]
                                for i in self.tree.get_children()
                            ]
                        except Exception:
                            existing = []
                        for k, v in ur.items():
                            name = k
                            try:
                                if name not in existing:
                                    self.tree.insert(
                                        "", "end", text=name, values=("", "")
                                    )
                                self.apply_listing(name, v)
                            except Exception as e:
                                logger.log(
                                    "UI", f"unpack_results 초기 적용 실패: {name} {e}"
                                )

                    self.parent.after(2, _apply_all_unpack_results)
            except Exception as e:
                logger.log("UI", f"unpack_results 조회 실패: {e}")

    # ---------------------------------------------------------------------
    def insert_pcks(self, entries: List[Dict[str, Any]]) -> None:
        """트리에 PCK 이름 목록을 갱신합니다.

        entries 형식: List[Dict], 각 Dict는 최소 {'name': <str>} 를 포함합니다.
        이 메서드는 UI 상태만 갱신하며 storage에 쓰지 않습니다.
        """
        if not isinstance(entries, list):
            logger.log("UI", "insert_pcks: entries가 리스트가 아님")
            return

        # 모든 기존 루트 항목 제거 후 재삽입 (간단하고 일관된 동작)
        for iid in list(self.tree.get_children()):
            self.tree.delete(iid)

        for e in entries:
            if not isinstance(e, dict):
                continue
            name = e.get("name")
            if not name:
                continue
            # 루트 항목으로 삽입. 추가 메타가 필요하면 values에 넣어 확장 가능
            self.tree.insert("", "end", text=name, values=("", ""))

    # ---------------------------------------------------------------------
    def get_selected_names(self) -> List[str]:
        """현재 선택된(또는 선택이 없으면 전체) 루트 항목 이름 목록을 반환합니다.

        반환 값: List[str]
        """
        items = self.tree.selection()
        if not items:
            items = self.tree.get_children()
        names: List[str] = []
        for iid in items:
            it = self.tree.item(iid)
            name = it.get("text")
            if name:
                names.append(name)
        return names

    # ---------------------------------------------------------------------
    def apply_listing(self, pck_name: str, listing: Dict[str, Any]) -> None:
        """특정 PCK 노드에 대해 상세 listing을 적용합니다.

        예상되는 listing 구조 예시:
        {
            'wem': [ {'name': 'sound1.wem'}, ... ],
            'bnk': [ {'bnk_folder': 'folder', 'files':[{'name':'file1'},{...}]}, ... ]
        }

        동작:
        - pck_name에 해당하는 루트 노드를 찾아 자식 목록을 모두 삭제
        - listing['wem'] 항목들은 루트의 자식으로 추가
        - listing['bnk'] 항목들은 폴더 노드로 추가하고 내부 파일들을 추가
        """
        if not listing or not isinstance(listing, dict):
            return

        # 대상 루트 노드를 탐색
        target = None
        for iid in self.tree.get_children():
            if self.tree.item(iid).get("text") == pck_name:
                target = iid
                break
        if target is None:
            # 트리에 존재하지 않으면 무시
            return

        # 기존 자식 모두 제거
        for c in list(self.tree.get_children(target)):
            self.tree.delete(c)

        # WEM 파일 목록 추가
        for w in listing.get("wem", []):
            if isinstance(w, dict) and w.get("name"):
                self.tree.insert(target, "end", text=w.get("name"), values=("", ""))

        # BNK 폴더 및 내부 파일 추가
        for b in listing.get("bnk", []):
            if not isinstance(b, dict):
                continue
            folder = b.get("bnk_folder", "") + "/"
            folder_iid = self.tree.insert(target, "end", text=folder, values=("", ""))
            for f in b.get("files", []):
                if isinstance(f, dict) and f.get("name"):
                    self.tree.insert(
                        folder_iid, "end", text=f.get("name"), values=("", "")
                    )

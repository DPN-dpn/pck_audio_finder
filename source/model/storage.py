from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Callable
from util import logger

BASE_DIR = Path(__file__).resolve().parents[2]
# persist storage inside the workspace `data` folder instead of project root
_DEFAULT_FILE = BASE_DIR / "data" / "storage.json"


class Storage:
    """프로젝트 전역에서 접근 가능한 간단한 저장소.

    - pck_list: 불러온 PCK 목록 (list of {"name": ..., "path": ..., "size": bytes})
    - unpack_results: pck_key -> {"bnk": [...], "wems": [...], ...}
    - wavs: wav_key -> {"type": "SFX"|"Voice"|..., "subtitle": str, ...}

    사용법 예:
        from model.storage import storage
        storage.add_pck({"name": "10100.pck", "path": "input_pck/10100.pck"})
        storage.set_wav_metadata("sound_001", {"type": "Voice", "subtitle": "안녕하세요"})
        storage.save()
    """

    def __init__(self, path: Optional[Path] = None):
        self._lock = RLock()
        self.path = Path(path) if path is not None else _DEFAULT_FILE
        self.pck_list: List[Dict[str, Any]] = []
        self.unpack_results: Dict[str, Dict[str, Any]] = {}
        self.wavs: Dict[str, Dict[str, Any]] = {}
        # listeners for pck_list changes: call(fn(pck_list: List[Dict]))
        self._pck_list_listeners: List = []
        # try load existing; 실패 시 로그를 남기고 빈 상태로 시작
        try:
            self.load()
        except Exception as e:
            logger.log("STORAGE", f"초기 로드 실패: {e}")

    # Persistence
    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                return
            text = self.path.read_text(encoding="utf-8")
            if not text:
                return
            data = json.loads(text)
            self.pck_list = data.get("pck_list", [])
            self.unpack_results = data.get("unpack_results", {})
            self.wavs = data.get("wavs", {})
            # notify listeners that pck_list was loaded (errors from listeners are logged)
            self._notify_pck_list()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "pck_list": self.pck_list,
                "unpack_results": self.unpack_results,
                "wavs": self.wavs,
            }
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # helpers to ensure size is set
    def _ensure_size(self, item: Dict[str, Any]) -> None:
        p = item.get("path")
        if not p:
            return
        p = Path(p)
        if not p.is_absolute():
            p = BASE_DIR / p
        try:
            if p.exists():
                item["size"] = int(p.stat().st_size)
        except OSError as e:
            logger.log("STORAGE", f"_ensure_size 파일정보 조회 실패: {e}")

    # PCK list helpers
    def set_pck_list(self, items: List[Dict[str, Any]]) -> None:
        with self._lock:
            self.pck_list = [dict(i) for i in items]
            for it in self.pck_list:
                if "size" not in it:
                    self._ensure_size(it)
            self.save()
        try:
            self._notify_pck_list()
        except Exception as e:
            logger.log("STORAGE", f"set_pck_list 리스너 알림 실패: {e}")

    def add_pck(self, item: Dict[str, Any]) -> None:
        with self._lock:
            it = dict(item)
            if "size" not in it:
                self._ensure_size(it)
            if it not in self.pck_list:
                self.pck_list.append(it)
                self.save()
        try:
            self._notify_pck_list()
        except Exception as e:
            logger.log("STORAGE", f"add_pck 리스너 알림 실패: {e}")

    def get_pck_list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(i) for i in self.pck_list]

    # Unpack results helpers
    def set_unpack_result(self, pck_key: str, result: Dict[str, Any]) -> None:
        with self._lock:
            self.unpack_results[pck_key] = result
            self.save()

    def get_unpack_result(self, pck_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.unpack_results.get(pck_key)

    # WAV metadata helpers
    def set_wav_metadata(self, wav_key: str, meta: Dict[str, Any]) -> None:
        with self._lock:
            existing = self.wavs.get(wav_key, {})
            existing.update(meta)
            self.wavs[wav_key] = existing
            self.save()

    def get_wav_metadata(self, wav_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            m = self.wavs.get(wav_key)
            return dict(m) if m is not None else None

    def find_wavs_by_type(self, wav_type: str) -> List[str]:
        with self._lock:
            return [k for k, v in self.wavs.items() if v.get("type") == wav_type]

    def clear(self) -> None:
        with self._lock:
            self.pck_list.clear()
            self.unpack_results.clear()
            self.wavs.clear()
            self.save()

    # Listener registration for pck list changes
    def register_pck_list_listener(self, fn) -> None:
        with self._lock:
            if fn not in self._pck_list_listeners:
                self._pck_list_listeners.append(fn)

    def unregister_pck_list_listener(self, fn) -> None:
        with self._lock:
            if fn in self._pck_list_listeners:
                self._pck_list_listeners.remove(fn)

    def _notify_pck_list(self) -> None:
        with self._lock:
            listeners = list(self._pck_list_listeners)
            data = [dict(i) for i in self.pck_list]
        for fn in listeners:
            try:
                fn(data)
            except Exception as e:
                logger.log("STORAGE", f"pck_list 리스너 실행 중 오류: {e}")


# module-level singleton for easy import
storage = Storage()

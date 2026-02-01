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
        # 이전 버전과의 호환을 위해 로드 시에 top-level `unpack_results`/`wavs`
        # 를 pck_list 내부로 마이그레이션합니다. 런타임에서는 pck_list에
        # 각 항목의 'unpack'의 'files' 리스트로 통합되어 사용됩니다.
        # listeners for pck_list changes: call(fn(pck_list: List[Dict]))
        self._pck_list_listeners: List[Callable[[List[Dict[str, Any]]], None]] = []
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
            # 기본적으로 pck_list를 불러옴
            self.pck_list = data.get("pck_list", [])
            # 이전 포맷(별도 unpack_results)에 데이터가 있으면 pck_list에 병합
            old_ur = data.get("unpack_results", {})
            if isinstance(old_ur, dict):
                for name, res in old_ur.items():
                    # 기존에 같은 name의 항목이 있으면 덮어쓰기
                    found = False
                    for it in self.pck_list:
                        if it.get("name") == name:
                            it["unpack"] = res
                            found = True
                            break
                    if not found:
                        self.pck_list.append({"name": name, "unpack": res})
            # 이전 포맷에서 top-level 'wavs'가 있으면 가능한 경우
            # pck_list 내부의 file 항목과 매칭하여 메타데이터를 병합합니다.
            old_wavs = data.get("wavs", {}) or {}
            if isinstance(old_wavs, dict) and old_wavs:
                merged = 0
                for wav_key, meta in old_wavs.items():
                    for it in self.pck_list:
                        unpack = it.get("unpack") or {}
                        # normalize wem->files if needed before matching
                        files = unpack.get("files")
                        if files is None and isinstance(unpack.get("wem"), list):
                            files = [dict(f) for f in unpack.get("wem")]
                            unpack["files"] = files
                            it["unpack"] = unpack
                        for f in (files or []):
                            name = f.get("name")
                            if name and (name == wav_key or Path(name).stem == wav_key):
                                f.update(meta)
                                merged += 1
                                break
                if merged:
                    logger.log("STORAGE", f"레거시 wavs 중 {merged}개를 pck_list로 병합")
            # notify listeners that pck_list was loaded (errors from listeners are logged)
            self._notify_pck_list()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                # Persist pck_list as the canonical storage format.
                    "pck_list": self.pck_list,
            }
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _find_pck_entry(self, name: str) -> Optional[Dict[str, Any]]:
        """`pck_list`에서 name에 해당하는 항목(참조)을 반환합니다."""
        for it in self.pck_list:
            if it.get("name") == name:
                return it
        return None

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
            # normalize incoming result: wem -> files
            r = dict(result)
            if "files" not in r and "wem" in r:
                r["files"] = [dict(x) for x in r.get("wem", [])]
                r.pop("wem", None)
            # pck_list에서 동일 name을 찾거나 새 항목으로 추가
            it = self._find_pck_entry(pck_key)
            if it is not None:
                it["unpack"] = r
            else:
                self.pck_list.append({"name": pck_key, "unpack": r})
            self.save()
        try:
            self._notify_pck_list()
        except Exception:
            pass

    def get_unpack_result(self, pck_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            it = self._find_pck_entry(pck_key)
            if it is None:
                return None
            val = it.get("unpack")
            if not isinstance(val, dict):
                return val
            # ensure legacy 'wem' converted
            if "files" not in val and "wem" in val:
                val = dict(val)
                val["files"] = [dict(x) for x in val.get("wem", [])]
                val.pop("wem", None)
            return dict(val)

    # WAV metadata helpers
    def set_wav_metadata(self, wav_key: str, meta: Dict[str, Any]) -> None:
        with self._lock:
            # pck_list 내부의 unpack.files에서 name으로 매칭하여 메타 업데이트
            for it in self.pck_list:
                unpack = it.get("unpack") or {}
                files = unpack.get("files") or []
                for f in files:
                    name = f.get("name")
                    if name and (name == wav_key or Path(name).stem == wav_key):
                        f.update(meta)
                        it["unpack"] = unpack
                        self.save()
                        try:
                            self._notify_pck_list()
                        except Exception:
                            pass
                        return
            # 찾지 못하면 pck_list에 새 항목으로 추가하여 모든 데이터가 pck_list에 있게 함
            new_entry = {"name": wav_key, "unpack": {"files": [{"name": wav_key, **meta}]}}
            self.pck_list.append(new_entry)
            self.save()
        try:
            self._notify_pck_list()
        except Exception:
            pass

    def get_wav_metadata(self, wav_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            # pck_list 내부 우선 탐색 (files.name 기준)
            for it in self.pck_list:
                unpack = it.get("unpack") or {}
                files = unpack.get("files") or []
                for f in files:
                    name = f.get("name")
                    if name and (name == wav_key or Path(name).stem == wav_key):
                        return dict(f)
            return None

    def find_wavs_by_type(self, wav_type: str) -> List[str]:
        with self._lock:
            res: List[str] = []
            # pck_list 내부 검색
            for it in self.pck_list:
                unpack = it.get("unpack") or {}
                for f in (unpack.get("files") or []):
                    if f.get("type") == wav_type and f.get("name"):
                        res.append(f.get("name"))
            return res

    def clear(self) -> None:
        with self._lock:
            self.pck_list.clear()
            self.save()
        try:
            self._notify_pck_list()
        except Exception:
            pass

    @property
    def unpack_results(self) -> Dict[str, Any]:
        with self._lock:
            out: Dict[str, Any] = {}
            for it in self.pck_list:
                name = it.get("name")
                if not name:
                    continue
                if "unpack" in it and it.get("unpack"):
                    v = it.get("unpack")
                    out[name] = dict(v) if isinstance(v, dict) else v
            return out

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

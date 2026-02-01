import os
import threading
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any
from util import logger
from model.storage import storage


def convert_wav(tree_manager, parent, overlay: object = None) -> None:
    """WEM 변환 진입점.

    현재는 오버레이를 표시하고 백그라운드 스레드에서 작업을 수행한 뒤
    오버레이를 숨기는 기본 동작만 구현합니다. 실제 변환/청크 분할 로직은
    이후에 추가하세요.
    """

    # 단순화된 오버레이 헬퍼
    def _overlay_show(
        msg: str, indeterminate: bool = False, maximum: float = 1.0
    ) -> None:
        if overlay is None:
            return
        try:
            parent.after(
                0,
                lambda: overlay.show(msg, maximum=maximum, indeterminate=indeterminate),
            )
        except Exception as e:
            logger.log("CONVERT", f"오버레이 표시 실패: {e}")

    def _overlay_hide() -> None:
        if overlay is None:
            return
        try:
            parent.after(1, lambda: overlay.hide())
        except Exception as e:
            logger.log("CONVERT", f"오버레이 숨김 실패: {e}")

    # helper: gather all .wem files from storage.unpack_results
    def _gather_wems(root: Path) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        ur = getattr(storage, "unpack_results", {}) or {}
        seen = set()
        for pck_name, res in ur.items():
            res = res or {}
            base = Path(pck_name).stem
            for f in res.get("files", []):
                name = f.get("name")
                if not name or not name.lower().endswith(".wem"):
                    continue
                wem_path = root / "data" / base / Path(name)
                key = str(wem_path).lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "pck": pck_name,
                        "name": name,
                        "wem": wem_path,
                        "wav": wem_path.with_suffix(".wav"),
                    }
                )

            for b in res.get("bnk", []):
                bfolder = b.get("bnk_folder")
                if not bfolder:
                    continue
                for f in b.get("files", []):
                    name = f.get("name")
                    if not name or not name.lower().endswith(".wem"):
                        continue
                    wem_path = root / "data" / base / bfolder / Path(name)
                    key = str(wem_path).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(
                        {
                            "pck": pck_name,
                            "name": name,
                            "wem": wem_path,
                            "wav": wem_path.with_suffix(".wav"),
                        }
                    )

        return out

    def _split_chunks(items: List[Any], n_chunks: int) -> List[List[Any]]:
        if n_chunks <= 1 or not items:
            return [list(items)]
        chunks: List[List[Any]] = [[] for _ in range(n_chunks)]
        for idx, it in enumerate(items):
            chunks[idx % n_chunks].append(it)
        # remove empty chunks
        return [c for c in chunks if c]

    def _update_progress(current: int, total: int) -> None:
        if overlay is None:
            return
        sub = f"[{current}/{total}]"
        frac = float(current) / float(total) if total and total > 0 else 1.0
        try:
            overlay.schedule(frac, "WAV 변환 중...", sub)
        except Exception as e:
            logger.log("CONVERT", f"오버레이 업데이트 실패: {e}")

    def _worker(
        ch: List[Dict[str, Any]],
        root: Path,
        processed_counter: Dict[str, int],
        total: int,
    ) -> None:
        # run vgmstream-cli from bundled lib directory so DLLs are found
        vgm_dir = root / "lib" / "vgmstream"
        exe = vgm_dir / "vgmstream-cli.exe"
        for item in ch:
            wem = item.get("wem")
            wav = item.get("wav")
            if wem is None or wav is None:
                processed_counter["n"] += 1
                _update_progress(processed_counter["n"], total)
                continue
            if not wem.exists():
                logger.log("CONVERT", f"WEM 파일 없음: {wem}")
                processed_counter["n"] += 1
                _update_progress(processed_counter["n"], total)
                continue

            wav.parent.mkdir(parents=True, exist_ok=True)

            converted = False
            try:
                if exe.exists():
                    cmd = [str(exe), "-o", str(wav), str(wem)]
                    subprocess.run(
                        cmd,
                        cwd=str(vgm_dir),
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    cmd = ["vgmstream-cli", "-o", str(wav), str(wem)]
                    subprocess.run(
                        cmd,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                converted = True
            except Exception as e:
                logger.log("CONVERT", f"WAV 변환 실패 {wem}: {e}")

            if converted and wav.exists():
                try:
                    wem.unlink()
                except Exception as e:
                    logger.log("CONVERT", f"WEM 삭제 실패 {wem}: {e}")

            processed_counter["n"] += 1
            _update_progress(processed_counter["n"], total)

    def _worker_thread():
        root = Path(__file__).resolve().parents[2]
        wem_list = _gather_wems(root)
        total = len(wem_list)
        logger.log("CONVERT", f"변환할 WEM 파일 수: {total}")

        _overlay_show("WAV 변환 준비 중...", indeterminate=False)

        if total == 0:
            # nothing to do
            _overlay_hide()
            return

        # decide worker count
        cpu = os.cpu_count() or 4
        max_workers = min(8, cpu)
        workers = min(max_workers, total)
        chunks = _split_chunks(wem_list, workers)
        logger.log("CONVERT", f"청크로 분할된 그룹 수 : {len(chunks)}")

        processed = {"n": 0}
        threads: List[threading.Thread] = []
        for ch in chunks:
            t = threading.Thread(
                target=_worker, args=(ch, root, processed, total), daemon=True
            )
            threads.append(t)
            t.start()

        # wait for threads
        for t in threads:
            try:
                t.join()
            except Exception:
                pass

        # 변환이 모두 완료되면 storage.unpack_results의 파일명들을 .wem -> .wav로 교체
        try:
            pck_list = getattr(storage, "pck_list", None)
            changed = False
            if isinstance(pck_list, list):
                for it in pck_list:
                    unpack = it.get("unpack") or {}
                    for f in unpack.get("files", []):
                        name = f.get("name")
                        if isinstance(name, str) and name.lower().endswith(".wem"):
                            f["name"] = name[:-4] + ".wav"
                            changed = True
                    for b in unpack.get("bnk", []):
                        for ff in b.get("files", []):
                            name = ff.get("name")
                            if isinstance(name, str) and name.lower().endswith(".wem"):
                                ff["name"] = name[:-4] + ".wav"
                                changed = True

                if changed:
                    try:
                        storage.save()
                        # notify registered listeners (UI) that pck_list changed
                        notify = getattr(storage, "_notify_pck_list", None)
                        if callable(notify):
                            notify()
                    except Exception as e:
                        logger.log("CONVERT", f"storage.save 실패: {e}")
        except Exception as e:
            logger.log("CONVERT", f"storage 업데이트 실패: {e}")
        logger.log("CONVERT", f"WEM -> WAV 변환 {total}개 완료")

        # 완료 후 오버레이 숨기기
        _overlay_hide()

    threading.Thread(target=_worker_thread, daemon=True).start()

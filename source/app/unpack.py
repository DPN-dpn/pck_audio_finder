import threading
from pathlib import Path
from typing import List, Dict, Any
from util import logger
from model.storage import storage

# 기본 청크 크기: 100 MiB
DEFAULT_CHUNK_BYTES = 100 * 1024 * 1024


def _show_initial_overlay(overlay, parent) -> None:
    """오버레이를 indeterminate 상태로 표시합니다 (UI 스레드에서 호출되어야 함)."""
    if overlay is None:
        return
    overlay.show("PCK 청크 구분 중...", maximum=1.0, indeterminate=True)


def _hide_overlay(overlay, parent) -> None:
    """오버레이를 숨깁니다. 항상 메인 스레드에서 숨기도록 `parent.after`로 예약합니다."""
    if overlay is None:
        return

    def _do_hide():
        try:
            overlay.hide()
        except Exception as e:
            logger.log("UNPACK", f"overlay.hide 실패: {e}")

    try:
        parent.after(1, _do_hide)
    except Exception:
        # parent.after 호출 불가 시 즉시 호출
        _do_hide()


def _prepare_output_dir(root: Path) -> Path:
    """출력용 data 디렉터리를 준비하여 반환합니다."""
    out_dir = root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _get_pck_items() -> List[Dict[str, Any]]:
    """저장소에서 PCK 항목 목록을 읽어 반환합니다. 실패 시 빈 리스트 반환."""
    try:
        return storage.get_pck_list() or []
    except Exception as e:
        logger.log("UNPACK", f"storage.get_pck_list 실패: {e}")
        return []


def _get_item_size(item: Dict[str, Any], root: Path) -> int:
    """항목의 파일 크기를 결정합니다.

    우선 item['size'] 필드를 사용하고 없으면 item['path']로 파일을 찾아 크기 조회.
    실패하면 0을 반환합니다.
    """
    if not isinstance(item, dict):
        return 0

    s = item.get("size")
    if s is not None:
        try:
            return int(s)
        except Exception:
            pass

    p = item.get("path")
    if not p:
        return 0
    pth = Path(p)
    if not pth.is_absolute():
        pth = root / pth
    if pth.exists():
        return int(pth.stat().st_size)
    return 0


def _chunk_pck_by_size(
    items: List[Dict[str, Any]], root: Path, max_chunk_bytes: int = DEFAULT_CHUNK_BYTES
) -> List[List[Dict[str, Any]]]:
    """크기 기준으로 PCK 항목들을 청크로 나눕니다.

    - 가능한 한 각 청크의 총합이 `max_chunk_bytes`를 넘지 않도록 그룹화합니다.
    - 단일 파일이 `max_chunk_bytes`보다 크면 그 파일은 단독 청크가 됩니다.
    """
    chunks: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cur_sum = 0

    for it in items:
        sz = _get_item_size(it, root)
        # 큰 단일 항목은 별도 청크로 처리
        if sz >= max_chunk_bytes:
            if cur:
                chunks.append(cur)
                cur = []
                cur_sum = 0
            chunks.append([it])
            continue

        if cur_sum + sz > max_chunk_bytes and cur:
            chunks.append(cur)
            cur = [it]
            cur_sum = sz
        else:
            cur.append(it)
            cur_sum += sz

    if cur:
        chunks.append(cur)
    return chunks


def _update_progress(overlay_obj, current: int, total_count: int) -> None:
    """오버레이에 진행도를 안전하게 갱신합니다 (디버깅을 위해 실패는 로깅)."""
    if overlay_obj is None:
        return
    sub = f"[{current}/{total_count}]"
    try:
        frac = (
            float(current) / float(total_count)
            if total_count and total_count > 0
            else 1.0
        )
    except Exception:
        frac = 1.0
    try:
        overlay_obj.schedule(frac, "PCK 언팩 중...", sub)
    except Exception as e:
        logger.log("UNPACK", f"오버레이 업데이트 실패: {e}")


def unpack_pck(tree_manager, parent, overlay: object = None) -> None:
    """PCK 목록을 가져와 용량 기준으로 청크를 나눈 뒤(로그만 남김) 오버레이를 닫습니다.

    현재 함수는 청크 분할과 로그 기록까지만 수행하며, 실제 언팩 로직은
    `_process_pck_item` 등으로 분리하여 나중에 추가할 수 있도록 설계되어 있습니다.
    """
    # UI 표시
    try:
        _show_initial_overlay(overlay, parent)
    except Exception as e:
        logger.log("UNPACK", f"오버레이 표시 실패: {e}")

    def _unpack_chunk(
        chunk_items: List[Dict[str, Any]],
        root: Path,
        out_dir: Path,
        overlay_obj,
        parent_obj,
        processed_counter: Dict[str, int],
        total_count: int,
    ) -> None:
        """주어진 청크의 PCK 항목들을 언팩해서 `out_dir`에 저장.

        - `processed_counter`는 {'n': int} 형태의 가변 카운터로, 처리된 파일 수를
          증가시키며 메인 오버레이에 진행을 보고합니다.
        - overlay_obj는 ProgressOverlay 인스턴스(또는 유사 API)를 가정합니다.
        """
        # 런타임으로 HoyoAudioTools 라이브러리 경로를 추가하고 필요한 클래스 임포트
        try:
            import sys

            lib_path = root / "lib" / "HoyoAudioTools" / "lib"
            if str(lib_path) not in sys.path:
                sys.path.insert(0, str(lib_path))
            from HoyoPckExtractor import PCKextract
            from BNKcompiler import BNK
        except Exception as e:
            logger.log("UNPACK", f"HoyoAudioTools 임포트 실패: {e}")
            return

        for item in chunk_items:
            # pck 파일 경로 결정
            path_str = item.get("path") or item.get("name")
            if not path_str:
                logger.log("UNPACK", f"항목에 경로 없음: {item}")
                continue
            pth = Path(path_str)
            if not pth.is_absolute():
                pth = root / pth
            if not pth.exists():
                logger.log("UNPACK", f"PCK 파일 존재하지 않음: {pth}")
                processed_counter["n"] += 1
                _update_progress(overlay_obj, processed_counter["n"], total_count)
                continue

            # 출력 서브디렉터리: data/<pck_name_without_ext>/
            name = item.get("name") or pth.name
            base_name = Path(name).stem
            target_dir = out_dir / base_name
            # 이미 결과 폴더가 존재하고 비어있지 않으면 언팩이 완료된 것으로 간주하고 건너뜁니다.
            # 이미 결과물이 있으면 건너뜀
            try:
                if target_dir.exists() and any(target_dir.iterdir()):
                    logger.log(
                        "UNPACK", f"이미 언팩된 것으로 건너뜀: {target_dir.name}"
                    )
                    processed_counter["n"] += 1
                    _update_progress(overlay_obj, processed_counter["n"], total_count)
                    continue
            except Exception as e:
                logger.log("UNPACK", f"결과 폴더 검사 실패: {e}")

            target_dir.mkdir(parents=True, exist_ok=True)

            try:
                extractor = PCKextract(str(pth), str(target_dir))
                allfiles = extractor.extract()
            except Exception as e:
                logger.log("UNPACK", f"PCK 언팩 실패 {pth}: {e}")
                processed_counter["n"] += 1
                _update_progress(overlay_obj, processed_counter["n"], total_count)
                continue

            # allfiles: dict of relative path -> bytes
            wem_list = []
            bnk_list = []
            for rel, data in allfiles.items():
                outpath = target_dir / rel
                try:
                    if rel.lower().endswith(".bnk"):
                        bnk_obj = BNK(bytes=data)
                        if bnk_obj.data.get("DATA") is not None:
                            bnk_folder = target_dir / (Path(rel).stem + "_bnk")
                            bnk_folder.mkdir(parents=True, exist_ok=True)
                            bnk_obj.extract("all", str(bnk_folder))
                            # 수집: BNK 폴더에 생성된 파일 목록을 즉시 수집
                            files = []
                            for f in bnk_folder.iterdir():
                                if f.is_file():
                                    files.append({"name": f.name})
                            bnk_list.append(
                                {"bnk_folder": bnk_folder.name, "files": files}
                            )
                    else:
                        outpath.parent.mkdir(parents=True, exist_ok=True)
                        with open(outpath, "wb") as f:
                            f.write(data)
                        # WEM 파일이면 즉시 목록에 추가
                        if outpath.suffix.lower() == ".wem":
                            relp = outpath.relative_to(target_dir)
                            wem_list.append({"name": str(relp).replace("\\", "/")})
                except Exception as e:
                    logger.log("UNPACK", f"파일 기록 실패 {rel}: {e}")

            # 추출 결과를 스토리지에 저장 (pck -> wem / bnk 구조)
            listing = {"wem": wem_list, "bnk": bnk_list}
            try:
                storage.set_unpack_result(f"{base_name}.pck", listing)
            except Exception as e:
                logger.log("UNPACK", f"storage에 언팩 결과 저장 실패: {e}")

            # UI에 바로 반영 (메인 스레드에서)
            try:
                if tree_manager is not None:
                    try:
                        parent_obj.after(
                            1,
                            lambda bn=name, lst=listing: tree_manager.apply_listing(
                                bn, lst
                            ),
                        )
                    except Exception:
                        tree_manager.apply_listing(name, listing)
            except Exception as e:
                logger.log("UNPACK", f"트리에 언팩 결과 적용 실패: {e}")

            # 처리 카운터 증가 및 진행 갱신
            processed_counter["n"] += 1
            _update_progress(overlay_obj, processed_counter["n"], total_count)

    def worker():
        root = Path(__file__).resolve().parents[2]
        out_dir = _prepare_output_dir(root)

        pck_items = _get_pck_items()
        logger.log("UNPACK", f"발견된 PCK 파일: {len(pck_items)}개")

        # 전체 항목 수 (진행도 기준)
        total_files = len(pck_items) if pck_items else 0

        # 오버레이 전환은 UI 스레드에서 수행해야 안전합니다. 가능한 경우
        # `parent.after`로 예약해 메인 스레드에서 실행하도록 합니다.
        try:
            if overlay is not None:
                try:
                    # ProgressOverlay는 fraction(0..1) 방식으로 사용되도록 설계되어
                    # 있으므로 determinate 모드의 maximum을 1.0으로 설정합니다.
                    parent.after(
                        0,
                        lambda: overlay.show(
                            "PCK 언팩 중...", maximum=1.0, indeterminate=False
                        ),
                    )
                except Exception:
                    # `after`가 사용 불가하면 직접 호출 시도
                    overlay.show("PCK 언팩 중...", maximum=1.0, indeterminate=False)
        except Exception as e:
            logger.log("UNPACK", f"오버레이 전환 실패: {e}")

        # 청크 단위로 처리
        chunks = _chunk_pck_by_size(pck_items, root)
        logger.log("UNPACK", f"청크로 분할된 그룹 수: {len(chunks)}")
        processed = {"n": 0}
        for ch in chunks:
            _unpack_chunk(ch, root, out_dir, overlay, parent, processed, total_files)
        logger.log("UNPACK", f"PCK 언팩 {len(pck_items)}개 완료")

        # 완료 후 오버레이 숨기기(메인 스레드에서)
        _hide_overlay(overlay, parent)

    threading.Thread(target=worker, daemon=True).start()

from pathlib import Path
from datetime import datetime
from util import logger, config
import shutil
import json
import os
from tkinter import filedialog
import json
import os


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


def copy_selected_pcks_to_temp(tree, path_var) -> tuple:
    """선택된(또는 트리에 로드된) PCK 파일들을 시스템 임시 폴더 아래
    `pck_audio_finder_temp/input_pck`로 복사합니다. 기존 내용을 삭제하고 새로 복사합니다.

    반환: (input_pck_path, [filenames])
    """
    try:
        src_folder = Path(path_var.get()) if path_var and path_var.get() else Path.cwd()
    except Exception:
        src_folder = Path.cwd()

    # use project's temp folder (workspace_root/temp/input_pck)
    try:
        workspace_root = Path(__file__).resolve().parents[2]
    except Exception:
        workspace_root = Path.cwd()
    temp_root = workspace_root / 'temp'
    input_pck_dir = temp_root / 'input_pck'
    # remove previous input_pck contents only
    if input_pck_dir.exists():
        try:
            shutil.rmtree(input_pck_dir)
        except Exception:
            pass
    input_pck_dir.mkdir(parents=True, exist_ok=True)

    items = tree.selection()
    if not items:
        items = tree.get_children()

    copied = []
    for iid in items:
        try:
            vals = tree.item(iid).get('values') or ()
            name = vals[0] if vals else None
            if not name:
                continue
            src = src_folder / name
            if src.exists() and src.is_file():
                shutil.copy2(src, input_pck_dir / src.name)
                copied.append(src.name)
            else:
                logger.log("PCK", f"파일이 존재하지 않음: {src}")
        except Exception as e:
            logger.log("PCK", f"복사 실패: {e}")

    logger.log("PCK", f"{input_pck_dir}으로 {len(copied)}개 파일을 복사했습니다")
    return (str(input_pck_dir), copied)


def browse(tree, path_var):
    """UI에서 사용하는 디렉터리 선택 로직을 앱 계층으로 이동한 함수.

    - `tree`: tkinter Treeview 인스턴스
    - `path_var`: tkinter StringVar 인스턴스
    """
    # 저장된 마지막 경로가 유효하면 초기 디렉터리로 사용합니다
    last = config.get_str("ui", "last_path", fallback="")
    if last and Path(last).exists():
        initial = last
    else:
        initial = str(Path.cwd())
    p = filedialog.askdirectory(initialdir=initial)
    if p:
        path_var.set(p)
        config.set_str("ui", "last_path", p)
        # 경로가 변경되면 이전에 불러온 데이터(트리)를 초기화합니다
        try:
            for iid in tree.get_children():
                tree.delete(iid)
        except Exception:
            pass
        logger.log("UI", f"경로를 변경하여 로드된 데이터를 초기화했습니다: {p}")


def extract_wav(tree, path_var):
    """UI의 WAV 추출 버튼 동작을 앱 계층으로 이동한 함수.

    - 복사 -> 언팩 -> JSON 생성의 전체 흐름을 관리합니다.
    """
    dest, copied = copy_selected_pcks_to_temp(tree, path_var)
    if not copied:
        logger.log("UI", "복사할 PCK 파일이 없습니다")
        return
    logger.log("UI", f"PCK 파일을 복제했습니다: {dest}")
    for n in copied:
        logger.log("UI", f"  {n}")

    # 복사된 PCK들을 하나씩 data 폴더로 언팩하고 구조 JSON을 생성합니다
    try:
        jsons = unpack_copied_pcks_to_data(dest, copied)
        if not jsons:
            logger.log("UI", "언팩 또는 JSON 생성된 항목이 없습니다")
            return
        logger.log("UI", "언팩 및 JSON 생성 완료:")
        for j in jsons:
            logger.log("UI", f"  {j}")
    except Exception as e:
        logger.log("UI", f"언팩 처리 중 오류: {e}")


def unpack_copied_pcks_to_data(temp_input_dir: str, filenames: list) -> list:
    """주어진 temp/input_pck 폴더의 PCK 파일들을 하나씩 `data` 폴더로 언팩하고,
    각 PCK마다 구조를 설명하는 JSON 파일을 `data`에 작성합니다.

    반환: 생성된 JSON 파일 경로들의 리스트
    """
    workspace_root = Path(__file__).resolve().parents[2]
    data_dir = workspace_root / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for name in filenames:
        try:
            src = Path(temp_input_dir) / name
            if not src.exists():
                logger.log('PCK', f'언팩 실패, 파일 없음: {src}')
                continue

            # import here to avoid circular imports at module load
            try:
                from app.unpack import extract_pck_file
            except Exception:
                from unpack import extract_pck_file

            rc = extract_pck_file(str(src))
            if rc != 0:
                logger.log('PCK', f'언팩 실패 코드 {rc}: {src.name}')
                continue

            # 원래 언팩 경로는 pck 파일과 같은 폴더에 생성됨
            unpacked = src.parent / (src.stem + '_unpacked')
            target = data_dir / (src.stem + '_unpacked')

            # 이동: 기존 대상이 있으면 삭제 후 이동
            if target.exists():
                try:
                    shutil.rmtree(target)
                except Exception:
                    pass
            try:
                shutil.move(str(unpacked), str(target))
            except Exception as e:
                logger.log('PCK', f'언팩 결과 이동 실패: {e}')

            # 구조 수집: BNK 폴더 목록과 루트의 WEM 파일
            bnk_infos = []
            if target.exists():
                for child in target.iterdir():
                    if child.is_dir() and child.name.lower().endswith('_bnk'):
                        files = [str(p.relative_to(child)) for p in child.rglob('*') if p.is_file()]
                        bnk_infos.append({'bnk_folder': child.name, 'files': files})

            wem_files = []
            if target.exists():
                for p in target.iterdir():
                    if p.is_file():
                        wem_files.append(p.name)

            json_obj = {
                'pck': name,
                'unpacked_to': str(target),
                'bnk': bnk_infos,
                'wem': wem_files
            }

            json_path = data_dir / (src.stem + '.json')
            try:
                with open(json_path, 'w', encoding='utf-8') as jf:
                    json.dump(json_obj, jf, ensure_ascii=False, indent=2)
                results.append(str(json_path))
                logger.log('PCK', f'구조 JSON 생성: {json_path}')
            except Exception as e:
                logger.log('PCK', f'JSON 작성 실패: {e}')

        except Exception as e:
            logger.log('PCK', f'언팩 처리 중 예외: {e}')

    return results


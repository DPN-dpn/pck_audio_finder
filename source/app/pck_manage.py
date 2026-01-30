from pathlib import Path
from datetime import datetime
from util import logger, config
import shutil
import json
import os


"""앱 레벨의 PCK 관리기능 — UI와 분리된 순수 로직 모듈.

함수:
- load_pcks(folder=None) -> list[dict]: 지정 폴더(또는 설정의 마지막 경로)의 .pck 목록을 반환
- copy_selected_pcks_to_temp(src_folder, filenames) -> (temp_dir, copied_list): 파일 복사
- unpack_copied_pcks_to_data(temp_input_dir, filenames) -> list[json_paths]: pck 언팩 및 data로 이동, JSON 생성
"""


def load_pcks(folder: str = None, progress_cb=None) -> list:
    """폴더에서 .pck 파일 목록을 수집하여 메타정보 리스트로 반환합니다.

    각 항목은 {'name', 'size', 'modified'} 형태입니다.
    """
    # 경로 결정
    if folder:
        folder_path = Path(folder)
    else:
        # default to project's input_pck (fixed, not under temp)
        try:
            workspace_root = Path(__file__).resolve().parents[2]
            folder_path = workspace_root / 'input_pck'
            # ensure folder exists
            folder_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            folder_path = Path.cwd()

    try:
        pck_files = [x for x in folder_path.iterdir() if x.is_file() and x.suffix.lower() == ".pck"]
    except Exception:
        pck_files = []

    if not pck_files:
        logger.log("PCK", f"{folder_path}에서 .pck 파일을 찾을 수 없습니다")
        return []

    logger.log("PCK", f"{folder_path}에서 {len(pck_files)}개의 .pck 파일을 찾았습니다:")
    results = []
    total = len(pck_files)
    for idx, f in enumerate(pck_files):
        try:
            st = f.stat()
            size = st.st_size
            modified = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            size = 0
            modified = ""
        results.append({"name": f.name, "size": size, "modified": modified})
        logger.log("PCK", f"  {f.name}")
        # progress callback: fraction 0..1 and optional message
        try:
            if progress_cb and total:
                progress_cb((idx + 1) / total, f"로딩 PCK {idx+1}/{total}")
        except Exception:
            pass

    # final overall progress
    try:
        if progress_cb:
            progress_cb(1.0, '전체 완료')
    except Exception:
        pass

    return results

    


def copy_selected_pcks_to_temp(src_folder: str, filenames: list) -> tuple:
    """`src_folder`에 있는 `filenames`를 프로젝트의 `temp/input_pck`로 복사합니다.

    반환: (input_pck_dir:str, copied_names:list)
    """
    try:
        src_folder = Path(src_folder) if src_folder else Path.cwd()
    except Exception:
        src_folder = Path.cwd()

    try:
        workspace_root = Path(__file__).resolve().parents[2]
    except Exception:
        workspace_root = Path.cwd()
    input_pck_dir = workspace_root / 'input_pck'

    # 이전 내용 제거
    if input_pck_dir.exists():
        try:
            shutil.rmtree(input_pck_dir)
        except Exception:
            pass
    input_pck_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for name in filenames:
        try:
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


def unpack_copied_pcks_to_data(temp_input_dir: str, filenames: list, progress_cb=None) -> list:
    """temp/input_pck의 PCK들을 하나씩 언팩하여 프로젝트의 `data` 폴더로 이동하고,
    각 PCK별 구조를 JSON으로 기록합니다. 반환값은 생성된 JSON 파일 경로 리스트입니다.
    """
    workspace_root = Path(__file__).resolve().parents[2]
    data_dir = workspace_root / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total_files = len(filenames)
    # allocate more weight to the unpack step which reports internal progress
    # steps per file: start(1) + unpack_span(n) + json(1)
    steps_per_file = 20
    total_steps = max(1, total_files * steps_per_file)
    step = 0
    for name_idx, name in enumerate(filenames):
        try:
            src = Path(temp_input_dir) / name
            target = data_dir / (Path(name).stem + '_unpacked')

            # STEP: start processing this file
            step += 1
            try:
                if progress_cb:
                    progress_cb(step / total_steps, f"처리 시작: {name}")
            except Exception:
                pass

            # If target unpacked folder already exists in data, treat as already extracted
            if target.exists():
                logger.log('PCK', f'이미 언팩된 폴더가 존재하여 언팩을 건너뜁니다: {target}')
                # advance the step to near-completion for this file (skip unpack span)
                unpack_span = steps_per_file - 3
                step += unpack_span
                try:
                    if progress_cb:
                        progress_cb(min(1.0, step / total_steps), f"이미 언팩됨: {name}")
                except Exception:
                    pass
            else:
                # ensure source exists before attempting unpack
                if not src.exists():
                    logger.log('PCK', f'언팩 실패, 파일 없음: {src}')
                    # advance steps even on failure
                    step += 2
                    try:
                        if progress_cb:
                            progress_cb(min(1.0, step / total_steps), f"파일 없음: {name}")
                    except Exception:
                        pass
                    continue

                # unpack 함수를 동적으로 import (앱의 unpack.py 사용)
                try:
                    from app.unpack import extract_pck_file
                except Exception:
                    from unpack import extract_pck_file

                # pass an inner progress callback that maps inner unpack progress to overall progress
                step_at_unpack = step
                unpack_span = steps_per_file - 3

                def _inner_progress(frac, message=None):
                    try:
                        f = float(frac or 0.0)
                        overall = (step_at_unpack + f * unpack_span) / total_steps
                        if progress_cb:
                            progress_cb(min(1.0, overall), message or f"언팩 중: {name}")
                    except Exception:
                        pass

                rc = extract_pck_file(str(src), progress_cb=_inner_progress)
                if rc != 0:
                    logger.log('PCK', f'언팩 실패 코드 {rc}: {src.name}')
                    # advance steps on failure
                    # move to end of this file's allocated steps to reflect failure
                    step += (steps_per_file - 1)
                    try:
                        if progress_cb:
                            progress_cb(min(1.0, step / total_steps), f"언팩 실패: {name}")
                    except Exception:
                        pass
                    continue

                # 원래 언팩 경로는 pck 파일과 같은 폴더에 생성됨
                unpacked = src.parent / (src.stem + '_unpacked')

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

                # after move: move step to end of unpack span
                step = step_at_unpack + unpack_span
                try:
                    if progress_cb:
                        progress_cb(min(1.0, step / total_steps), f"언팩 완료: {name}")
                except Exception:
                    pass

            # 구조 수집: BNK 폴더 목록과 루트의 WEM 파일
            try:
                if progress_cb:
                    progress_cb(min(1.0, (step + 0.1) / total_steps), f"구조 수집 시작: {name}")
            except Exception:
                pass

            # Collect BNK folders and their files, storing empty metadata for
            # `category` and `subtitle` so the JSON schema already contains
            # those fields for future enrichment.
            bnk_infos = []
            if target.exists():
                for child in target.iterdir():
                    if child.is_dir() and child.name.lower().endswith('_bnk'):
                        files = []
                        for p in child.rglob('*'):
                            if p.is_file():
                                rel = str(p.relative_to(child))
                                files.append({'name': rel, 'category': '', 'subtitle': ''})
                        bnk_infos.append({'bnk_folder': child.name, 'files': files})

            # Collect root WEM files with empty metadata fields
            wem_files = []
            if target.exists():
                for p in target.iterdir():
                    if p.is_file():
                        wem_files.append({'name': p.name, 'category': '', 'subtitle': ''})

            try:
                # report mid-structure progress
                if progress_cb:
                    progress_cb(min(1.0, (step + 0.3) / total_steps), f"구조 수집 완료: {name}")
            except Exception:
                pass

            json_obj = {
                'pck': name,
                'unpacked_to': str(target),
                'bnk': bnk_infos,
                'wem': wem_files
            }

            json_path = data_dir / (src.stem + '.json')
            try:
                if progress_cb:
                    try:
                        progress_cb(min(1.0, (step + 0.4) / total_steps), f"JSON 작성 중: {name}")
                    except Exception:
                        pass
                with open(json_path, 'w', encoding='utf-8') as jf:
                    json.dump(json_obj, jf, ensure_ascii=False, indent=2)
                results.append(str(json_path))
                logger.log('PCK', f'구조 JSON 생성: {json_path}')
            except Exception as e:
                logger.log('PCK', f'JSON 작성 실패: {e}')

            # step: JSON written (final step for this file)
            step += 1
            try:
                if progress_cb:
                    progress_cb(min(1.0, step / total_steps), f"JSON 생성: {name}")
            except Exception:
                pass

            # step: tree update reflection
            step += 1
            try:
                if progress_cb:
                    progress_cb(min(1.0, step / total_steps), f"트리 반영: {name}")
            except Exception:
                pass

        except Exception as e:
            logger.log('PCK', f'언팩 처리 중 예외: {e}')

    return results


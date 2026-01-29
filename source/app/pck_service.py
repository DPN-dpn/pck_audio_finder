from pathlib import Path
from typing import List, Tuple
from util import config


"""`app.pck_service` 모듈은 함수형 API를 제공하여
UI 및 다른 모듈에서 일관되게 호출할 수 있도록 합니다.
"""


def get_config_folder() -> Path:
    """설정(config.ini)의 `ui.last_path`를 반환하거나, 없으면 현재 작업 디렉터리를 반환합니다."""
    p = config.get_str("ui", "last_path", fallback="")
    if p and Path(p).exists():
        return Path(p)
    return Path.cwd()


def list_pck_files() -> List[Path]:
    """설정된 폴더에서 `.pck` 파일 경로 목록을 반환합니다."""
    folder = get_config_folder()
    return [x for x in folder.iterdir() if x.is_file() and x.suffix.lower() == ".pck"]


def load_pcks() -> Tuple[Path, List[Path]]:
    """(폴더경로, .pck파일목록) 튜플을 반환합니다.

    파일시스템 접근 로직을 앱 계층에 모아두어 UI는 단순히 결과만 소비합니다.
    """
    folder = get_config_folder()
    files = list_pck_files()
    return folder, files

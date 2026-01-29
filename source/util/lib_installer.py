import os
import json
import shutil
import zipfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, Any

# Concrete specs for requested libs
LIB_SPECS = [
    # vgmstream release asset (win64 zip)
    {
        "type": "release",
        "owner": "vgmstream",
        "repo": "vgmstream",
        "asset_name": "vgmstream-win64.zip",
        "dest": "lib/vgmstream"
    },
    # HoyoAudioTools repository (zip of default branch)
    {
        "type": "repo",
        "owner": "failsafe42",
        "repo": "HoyoAudioTools",
        "branch": "main",
        "dest": "lib/HoyoAudioTools"
    }
]

HEADERS = {"User-Agent": "pck_audio_finder"}


def _download(url: str, target: Path):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as res, open(target, "wb") as out:
        shutil.copyfileobj(res, out)


def _extract_zip(zip_path: Path, dest_dir: Path):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest_dir)


def _download_release_asset(owner: str, repo: str, asset_name: str, dest: Path) -> bool:
    api = f"https://api.github.com/repos/{owner}/{repo}/releases"
    req = urllib.request.Request(api, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            releases = json.load(resp)
    except Exception:
        return False

    # search releases for matching asset name
    for r in releases:
        assets = r.get("assets", [])
        for a in assets:
            name = a.get("name", "")
            if name == asset_name:
                url = a.get("browser_download_url")
                if not url:
                    continue
                dest.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory() as td:
                    tmpf = Path(td) / name
                    _download(url, tmpf)
                    if tmpf.suffix.lower() == ".zip":
                        _extract_zip(tmpf, dest)
                    else:
                        shutil.move(str(tmpf), str(dest / name))
                return True
    return False


def _download_repo_zip(owner: str, repo: str, branch: str, dest: Path) -> bool:
    branches = [branch] if branch else ["main", "master"]
    for b in branches:
        url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{b}.zip"
        try:
            with tempfile.TemporaryDirectory() as td:
                tmpf = Path(td) / f"{repo}-{b}.zip"
                _download(url, tmpf)
                with tempfile.TemporaryDirectory() as ed:
                    _extract_zip(tmpf, Path(ed))
                    extracted = list(Path(ed).iterdir())
                    if not extracted:
                        continue
                    src = extracted[0]
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.move(str(src), str(dest))
                return True
        except Exception:
            continue
    return False


def ensure_libs(specs=None):
    """Ensure required libs present under project `lib/` directory.

    - Downloads `vgmstream-win64.zip` release asset from the vgmstream repo and
      extracts into `lib/vgmstream`.
    - Downloads repository zip for `failsafe42/HoyoAudioTools` into `lib/HoyoAudioTools`.

    This function is safe to call repeatedly; it will skip existing non-empty targets.
    """
    specs = specs or LIB_SPECS
    base = Path.cwd()
    for s in specs:
        dest = base / s.get("dest", "")
        if dest.exists() and any(dest.iterdir()):
            continue
        typ = s.get("type")
        owner = s.get("owner")
        repo = s.get("repo")
        if typ == "release":
            asset_name = s.get("asset_name")
            try:
                ok = _download_release_asset(owner, repo, asset_name, dest)
            except Exception:
                ok = False
            if not ok:
                dest.mkdir(parents=True, exist_ok=True)
        elif typ == "repo":
            branch = s.get("branch", "main")
            try:
                ok = _download_repo_zip(owner, repo, branch, dest)
            except Exception:
                ok = False
            if not ok:
                dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.mkdir(parents=True, exist_ok=True)

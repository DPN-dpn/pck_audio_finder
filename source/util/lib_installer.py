import json
import shutil
import zipfile
import tempfile
import urllib.request
from pathlib import Path

# Concrete specs for requested libs
LIB_SPECS = [
    # vgmstream release asset (win64 zip)
    {
        "type": "release",
        "owner": "vgmstream",
        "repo": "vgmstream",
        "asset_name": "vgmstream-win64.zip",
        "dest": "lib/vgmstream",
    },
    # HoyoAudioTools repository (zip of default branch)
    {
        "type": "repo",
        "owner": "failsafe42",
        "repo": "HoyoAudioTools",
        "branch": "main",
        "dest": "lib/HoyoAudioTools",
    },
]

HEADERS = {"User-Agent": "pck_audio_finder"}


def _log(msg: str):
    print(msg, flush=True)


def _download(url: str, target: Path):
    _log(f"Downloading {url} -> {target}")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as res, open(target, "wb") as out:
        shutil.copyfileobj(res, out)
    _log(f"Downloaded {target}")


def _extract_zip(zip_path: Path, dest_dir: Path):
    _log(f"Extracting {zip_path} -> {dest_dir}")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest_dir)
    _log(f"Extracted to {dest_dir}")


def _download_release_asset(owner: str, repo: str, asset_name: str, dest: Path) -> bool:
    api = f"https://api.github.com/repos/{owner}/{repo}/releases"
    req = urllib.request.Request(api, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            releases = json.load(resp)
    except Exception as e:
        _log(f"Failed to query releases for {owner}/{repo}: {e}")
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
                    _log(f"Found asset {name}, downloading...")
                    _download(url, tmpf)
                    if tmpf.suffix.lower() == ".zip":
                        _extract_zip(tmpf, dest)
                    else:
                        shutil.move(str(tmpf), str(dest / name))
                    _log(f"Installed release asset {asset_name} to {dest}")
                return True
    return False


def _download_repo_zip(owner: str, repo: str, branch: str, dest: Path) -> bool:
    branches = [branch] if branch else ["main", "master"]
    for b in branches:
        url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{b}.zip"
        _log(f"Attempting download of {owner}/{repo}@{b}")
        try:
            with tempfile.TemporaryDirectory() as td:
                tmpf = Path(td) / f"{repo}-{b}.zip"
                _download(url, tmpf)
                with tempfile.TemporaryDirectory() as ed:
                    _extract_zip(tmpf, Path(ed))
                    extracted = list(Path(ed).iterdir())
                    if not extracted:
                        _log(f"No files extracted for {owner}/{repo}@{b}")
                        continue
                    src = extracted[0]
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.move(str(src), str(dest))
                _log(f"Installed repo {repo}@{b} to {dest}")
                return True
        except Exception as e:
            _log(f"Failed to download {owner}/{repo}@{b}: {e}")
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
    # Use project root (two parents up from this file) so installer works
    # regardless of the current working directory when invoked.
    base = Path(__file__).resolve().parents[2]
    _log(f"Installer base directory: {base}")
    for s in specs:
        dest = base / s.get("dest", "")
        _log(f"Ensuring library at {dest}")
        if dest.exists() and any(dest.iterdir()):
            _log(f"Skipping existing {dest}")
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
                _log(f"Failed to install release asset {asset_name}; creating empty dir {dest}")
                dest.mkdir(parents=True, exist_ok=True)
        elif typ == "repo":
            branch = s.get("branch", "main")
            try:
                ok = _download_repo_zip(owner, repo, branch, dest)
            except Exception:
                ok = False
            if not ok:
                _log(f"Failed to install repo {owner}/{repo}@{branch}; creating empty dir {dest}")
                dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.mkdir(parents=True, exist_ok=True)
            _log(f"Created dir {dest} for unknown type {typ}")


if __name__ == "__main__":
    try:
        _log("lib_installer: starting ensure_libs()")
        ensure_libs()
        _log("lib_installer: done")
    except Exception as e:
        _log(f"lib_installer failed: {e}")

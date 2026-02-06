import os
import sys
import argparse
from pathlib import Path
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Try importing extractor; if not available, try to use bundled runtime
def ensure_hoyo_tools(runtime_path: str = None):
    """Return (PCKextract, BNK) classes.
    Prefer normal import. If import fails (e.g., syntax in library),
    load library source from bundled runtime and exec a patched copy
    in-memory without modifying files on disk.
    """
    try:
        from HoyoPckExtractor import PCKextract  # type: ignore
        from BNKcompiler import BNK  # type: ignore
        return PCKextract, BNK
    except Exception:
        pass

    candidates = []
    if runtime_path:
        candidates.append(Path(runtime_path) / 'Lib' / 'site-packages' / 'HoyoAudioTools' / 'lib')
    candidates.append(ROOT / 'runtime' / 'Lib' / 'site-packages' / 'HoyoAudioTools' / 'lib')
    candidates.append(HERE.parent / 'runtime' / 'Lib' / 'site-packages' / 'HoyoAudioTools' / 'lib')

    import importlib, types

    for cand in candidates:
        try:
            if not (cand and cand.exists()):
                continue

            # Ensure BNKcompiler can be imported from the candidate (we may keep cand on sys.path)
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
                added_path = True
            else:
                added_path = False

            try:
                BNKmod = importlib.import_module('BNKcompiler')
            except Exception:
                if added_path:
                    try: sys.path.remove(str(cand))
                    except Exception: pass
                continue

            # Load HoyoPckExtractor source text and apply an in-memory patch to fix
            # problematic f-string quoting without writing to disk.
            extractor_path = cand / 'HoyoPckExtractor.py'
            if not extractor_path.exists():
                if added_path:
                    try: sys.path.remove(str(cand))
                    except Exception: pass
                continue

            src = extractor_path.read_text(encoding='utf-8')
            # Patch the known problematic pattern (single-quoted f-string containing inner quotes).
            patched = src.replace("f'{int.from_bytes(id[::-1], 'big')}.{extension}'",
                                  "f\"{int.from_bytes(id[::-1], 'big')}.{extension}\"")

            mod = types.ModuleType('HoyoPckExtractor')
            mod.__file__ = str(extractor_path)
            try:
                exec(compile(patched, str(extractor_path), 'exec'), mod.__dict__)
                sys.modules['HoyoPckExtractor'] = mod
                PCKextract = mod.PCKextract
                BNK = BNKmod.BNK
                return PCKextract, BNK
            except Exception:
                # cleanup and continue to next candidate
                if 'HoyoPckExtractor' in sys.modules:
                    del sys.modules['HoyoPckExtractor']
                if added_path:
                    try: sys.path.remove(str(cand))
                    except Exception: pass
                continue

        except Exception:
            # try next candidate
            continue

    raise RuntimeError('HoyoAudioTools 패키지를 찾을 수 없습니다. runtime/Lib/site-packages에 설치되어 있는지 확인하세요.')


def find_pcks(input_dir: Path):
    for root, dirs, files in os.walk(input_dir):
        for f in files:
            if f.lower().endswith('.pck'):
                yield Path(root) / f


def unpack_one(pck_path: Path, out_base: Path, PCKextract, BNK):
    try:
        # Create output folder beside the .pck file with same name (without extension)
        outdir = pck_path.with_suffix('')
        if outdir.exists():
            # already unpacked (or folder exists) -> skip
            return True, f'스킵: {pck_path} -> {outdir}'
        outdir.mkdir(parents=True, exist_ok=True)

        allFiles = PCKextract(str(pck_path), str(outdir)).extract()

        # write files returned by extractor
        for filepath, data in allFiles.items():
            try:
                path_to_write = Path(filepath)
                if not path_to_write.is_absolute():
                    parts = list(path_to_write.parts)
                    # remove any number of leading common prefixes produced by extractor
                    while parts and parts[0] in (pck_path.name, pck_path.stem, 'input'):
                        parts.pop(0)
                    # if nothing left, use filename
                    if parts:
                        path_to_write = outdir.joinpath(*parts)
                    else:
                        path_to_write = outdir / pck_path.stem
                path_to_write.parent.mkdir(parents=True, exist_ok=True)
                with open(path_to_write, 'wb') as fh:
                    fh.write(data)
            except Exception:
                # skip writing this file but continue
                continue

        # handle any .bnk inside returned files by extracting their wems
        # scan written files for .bnk
        for root, dirs, files in os.walk(outdir):
            for f in files:
                if f.lower().endswith('.bnk'):
                    bnk_path = Path(root) / f
                    try:
                        with open(bnk_path, 'rb') as bf:
                            bdata = bf.read()
                        bnkObj = BNK(bytes=bdata)
                        if bnkObj.data.get('DATA') is not None:
                            bnk_out = bnk_path.with_suffix('')
                            bnk_out = Path(str(bnk_out) + '_bnk')
                            bnk_out.mkdir(parents=True, exist_ok=True)
                            bnkObj.extract('all', str(bnk_out))
                    except Exception:
                        continue
        return True, f'완료: {pck_path} -> {outdir}'
    except Exception as e:
        return False, f'{pck_path}: {e}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', default='input', help='input folder (recursive)')
    parser.add_argument('--output', '-o', default='unpacked', help='output base folder')
    parser.add_argument('--runtime', default=None, help='path to external runtime to use')
    parser.add_argument('--workers', type=int, default=0, help='number of worker threads (default: cpu_count)')
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        print('입력 폴더가 없습니다:', input_dir)
        return

    out_base = Path(args.output)
    out_base.mkdir(parents=True, exist_ok=True)

    try:
        PCKextract, BNK = ensure_hoyo_tools(args.runtime)
    except Exception as e:
        print('HoyoAudioTools 로드 실패:', e)
        return

    files = list(find_pcks(input_dir))
    if not files:
        print('처리할 pck 파일이 없습니다.')
        return

    workers = args.workers or max(1, multiprocessing.cpu_count())
    print(f'발견된 pck 파일: {len(files)}, 작업 스레드: {workers}')

    results = []
    total = len(files)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as exe:
        futures = {exe.submit(unpack_one, p, out_base, PCKextract, BNK): p for p in files}
        try:
            for fut in as_completed(futures):
                done += 1
                ok, msg = fut.result()
                # Normalize message prefix
                if ok:
                    print(f'[{done}/{total}] {msg}')
                else:
                    print(f'[{done}/{total}] 오류: {msg}')
        except KeyboardInterrupt:
            print('\n중단 요청 감지: 진행 중인 작업을 취소합니다...')


if __name__ == '__main__':
    main()

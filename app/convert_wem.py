"""convert_wem.py

Recursive .wem -> .wav converter using a local vgmstream package.

Usage examples:
  python app/convert_wem.py --input input
  python app/convert_wem.py --input input --site-packages runtime\Lib\site-packages --overwrite

The script will search the given input directory recursively for .wem files
and attempt to convert each to a .wav placed in the same directory.
It will try to import a `vgmstream` module from the provided
`--site-packages` path and use any available convert/decode function.
"""

import argparse
import os
import sys
import subprocess
import inspect
import multiprocessing
from typing import Optional

VERBOSE = True
_VGMSTREAM_MODULE = None


def find_wem_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith('.wem'):
                yield os.path.join(dirpath, fn)


def try_import_vgmstream(site_packages: Optional[str]):
    global _VGMSTREAM_MODULE

    if _VGMSTREAM_MODULE is not None:
        return _VGMSTREAM_MODULE

    if site_packages:
        site_packages = os.path.abspath(site_packages)
        if os.path.isdir(site_packages) and site_packages not in sys.path:
            sys.path.insert(0, site_packages)
    try:
        import importlib
        vgm = importlib.import_module('vgmstream')
        # Some distributions install vgmstream as a namespace package without a __file__.
        # Prefer to show the module file path if available, otherwise show the package path/spec.
        if VERBOSE:
            file_attr = getattr(vgm, '__file__', None)
            if file_attr:
                print(f"[정보] vgmstream 가져옴: {file_attr}")
            else:
                # try to show package path or spec
                pkg_path = getattr(vgm, '__path__', None)
                spec = getattr(vgm, '__spec__', None)
                if pkg_path:
                    print(f"[정보] vgmstream 패키지 경로: {list(pkg_path)}")
                elif spec:
                    print(f"[정보] vgmstream 모듈 스펙: {spec}")
                else:
                    print(f"[정보] vgmstream 가져옴(위치 알 수 없음)")
        _VGMSTREAM_MODULE = vgm
        return vgm
    except Exception as e:
        if VERBOSE:
            print(f"[디버그] vgmstream import 실패: {e}")
        return None


def decode_with_vgmstream_module(vgm, in_path: str, out_path: str):
    # Try a few likely function names and signatures.
    candidates = []
    for name, obj in inspect.getmembers(vgm, inspect.isroutine):
        candidates.append((name, obj))

    # Prefer functions that accept (infile, outfile)
    for name, func in candidates:
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.values())
            if len(params) >= 2:
                # try calling it with (in_path, out_path)
                try:
                    if VERBOSE:
                        print(f"[디버그] 시도: {vgm.__name__}.{name}(in, out)")
                    res = func(in_path, out_path)
                    # If it returns True or None it's likely successful.
                    if VERBOSE:
                        print(f"[정보] 호출됨: {vgm.__name__}.{name} -> {in_path}")
                    return 'module'
                except TypeError:
                    continue
                except Exception:
                    # continue trying other candidates
                    continue
        except (ValueError, TypeError):
            continue

    # If no candidate accepted (in,out) signature, try functions that return raw PCM bytes
    for name, func in candidates:
        try:
            sig = inspect.signature(func)
            if len(sig.parameters) == 1:
                try:
                    if VERBOSE:
                        print(f"[디버그] 시도: {vgm.__name__}.{name}(in) -> bytes")
                    data = func(in_path)
                    if isinstance(data, (bytes, bytearray)):
                        with open(out_path, 'wb') as f:
                            f.write(data)
                        return 'module'
                except Exception:
                    continue
        except Exception:
            continue

    return None


def decode_with_cli_tool(in_path: str, out_path: str, site_packages: Optional[str]):
    # Try to find a vgmstream CLI in the site_packages or in PATH
    candidates = []
    if site_packages:
        candidates.append(os.path.join(site_packages, 'vgmstream.exe'))
        candidates.append(os.path.join(site_packages, 'vgmstream-cli.exe'))
        candidates.append(os.path.join(site_packages, 'vgmstream'))
        # also check inside a vgmstream subfolder (where bundled exe and DLLs often live)
        candidates.append(os.path.join(site_packages, 'vgmstream', 'vgmstream-cli.exe'))
        candidates.append(os.path.join(site_packages, 'vgmstream', 'vgmstream.exe'))
    # fallback to just 'vgmstream' in PATH
    candidates.append('vgmstream')

    for cmd in candidates:
        try:
            # If cmd is a path to an exe, set cwd to its directory so DLLs are resolved
            work_dir = None
            exe = cmd
            if os.path.isabs(cmd) or os.path.sep in str(cmd):
                if os.path.exists(cmd):
                    work_dir = os.path.dirname(cmd)
                    exe = cmd

            # Use absolute paths for input/output so cwd doesn't affect file lookup
            abs_in = os.path.abspath(in_path)
            abs_out = os.path.abspath(out_path)

            # Some CLIs accept: vgmstream -o out.wav in.wem  (others: vgmstream in.wem out.wav)
            try_cmds = [ [exe, '-o', abs_out, abs_in], [exe, abs_in, abs_out] ]
            for tc in try_cmds:
                proc = subprocess.run(tc, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir)
                if proc.returncode == 0 and os.path.exists(abs_out):
                    return exe
                else:
                    if VERBOSE:
                        out = proc.stdout.decode(errors='ignore')
                        err = proc.stderr.decode(errors='ignore')
                        print(f"[디버그] CLI {exe} 종료 코드: {proc.returncode}")
                        if out:
                            print(f"[디버그] 표준출력:\n{out}")
                        if err:
                            print(f"[디버그] 표준에러:\n{err}")
        except FileNotFoundError:
            continue
        except Exception:
            continue

    return None


def convert_wem_to_wav(in_path: str, out_path: str, site_packages: Optional[str], overwrite: bool=False, idx: int = None, total: int = None) -> bool:
    # print skip if exists
    if os.path.exists(out_path) and not overwrite:
        if VERBOSE:
            if idx and total:
                print(f"[정보] [{idx}/{total}] 이미 존재하여 건너뜀: {out_path}")
            else:
                print(f"[정보] 이미 존재하여 건너뜀: {out_path}")
        return True

    # print start
    if VERBOSE:
        if idx and total:
            print(f"[정보] [{idx}/{total}] 변환 시작: {in_path} -> {out_path}")
        else:
            print(f"[정보] 변환 시작: {in_path} -> {out_path}")

    vgm = try_import_vgmstream(site_packages)
    if vgm:
        try:
            backend = decode_with_vgmstream_module(vgm, in_path, out_path)
            if backend and os.path.exists(out_path):
                if VERBOSE:
                    if idx and total:
                        print(f"[정보] [{idx}/{total}] 변환 완료: {in_path} -> {out_path}")
                    else:
                        print(f"[정보] 변환 완료: {in_path} -> {out_path}")
                return True
        except Exception as e:
            if VERBOSE:
                print(f"[디버그] vgmstream 모듈 디코드 예외: {e}")

    # fallback to CLI invocation
    backend = decode_with_cli_tool(in_path, out_path, site_packages)
    if backend:
        if VERBOSE:
            if idx and total:
                print(f"[정보] [{idx}/{total}] 변환 완료: {in_path} -> {out_path}")
            else:
                print(f"[정보] 변환 완료: {in_path} -> {out_path}")
        return True

    if VERBOSE:
        if idx and total:
            print(f"[오류] [{idx}/{total}] 변환 실패: {in_path}")
        else:
            print(f"[오류] 변환 실패: {in_path}")
    print(f"[오류] 변환 실패: {in_path}", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description='Convert .wem files to .wav using local vgmstream')
    parser.add_argument('--input', '-i', default='input', help='Input root directory to search')
    parser.add_argument('--site-packages', '-s', default=os.path.join('runtime', 'Lib', 'site-packages'),
                        help='Path to runtime\\Lib\\site-packages that contains vgmstream')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing .wav files')
    parser.add_argument('--quiet', action='store_true', help='Reduce logging output')
    parser.add_argument('--workers', '-w', type=int, default=1, help='Number of parallel worker processes (default 1)')
    args = parser.parse_args()

    global VERBOSE
    if args.quiet:
        VERBOSE = False

    root = args.input
    site_packages = args.site_packages

    # Note: vgmstream does not support GPU/CUDA acceleration; CPU workers are used.

    if not os.path.isdir(root):
        print(f"[오류] 입력 디렉터리가 존재하지 않습니다: {root}", file=sys.stderr)
        sys.exit(2)

    wems = list(find_wem_files(root))
    total = len(wems)
    success = 0

    if args.workers and args.workers > 1:
        if VERBOSE:
            print(f"[정보] 워커 프로세스 수: {args.workers}개")
        # ensure VERBOSE is visible to child processes
        VERBOSE_CHILD = VERBOSE
        tasks = [(wem, os.path.splitext(wem)[0] + '.wav', site_packages, args.overwrite, idx, total) for idx, wem in enumerate(wems, start=1)]
        with multiprocessing.Pool(processes=args.workers) as pool:
            for ok in pool.starmap(convert_wem_to_wav, tasks):
                if ok:
                    success += 1
    else:
        for idx, wem in enumerate(wems, start=1):
            out_wav = os.path.splitext(wem)[0] + '.wav'
            if convert_wem_to_wav(wem, out_wav, site_packages, overwrite=args.overwrite, idx=idx, total=total):
                success += 1

    if VERBOSE:
        print(f"[정보] 변환 완료: 성공 {success}/{total}")


if __name__ == '__main__':
    main()

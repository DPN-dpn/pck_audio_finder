import os
import sys
import argparse
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import traceback
import subprocess
import shutil
import glob
import time
import builtins

# Ensure local `lib` is on path for packages installed with `pip --target=lib`
HERE = Path(__file__).resolve().parent
LIB_DIR = HERE.parent / "lib"
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

# --- realtime logging: mirror prints to a UTF-8 log file immediately ---
ROOT = HERE.parent
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRANS_LOG = LOG_DIR / 'transcribe.log'

# If parent launcher sets this, child should NOT append to the log file
# to avoid duplicate lines when the parent's capturing stdout/stderr.
SKIP_CHILD_LOG = os.environ.get('TRANSCRIBE_SKIP_CHILD_LOG') == '1'

_orig_print = builtins.print
def print(*args, **kwargs):
    """Module-local print wrapper: writes to stdout (flushed) and appends to `logs/transcribe.log` in UTF-8."""
    # ensure flushed stdout for realtime console
    kwargs.setdefault('flush', True)
    try:
        _orig_print(*args, **kwargs)
    except Exception:
        # if stdout problematic, ignore
        pass

    # Build text similar to builtin.print
    sep = kwargs.get('sep', ' ')
    end = kwargs.get('end', '\n')
    try:
        text = sep.join(str(a) for a in args) + end
        # If the parent process is already capturing stdout/stderr into the
        # same log file, avoid appending again from the child to prevent
        # duplicated/garbled entries. Parent sets TRANSCRIBE_SKIP_CHILD_LOG=1.
        if not SKIP_CHILD_LOG:
            # append to log file as UTF-8
            try:
                with open(TRANS_LOG, 'a', encoding='utf-8') as lf:
                    lf.write(text)
                    lf.flush()
            except Exception:
                # fallback: try cp949 for Windows ANSI logs
                try:
                    with open(TRANS_LOG, 'a', encoding='cp949', errors='replace') as lf:
                        lf.write(text)
                        lf.flush()
                except Exception:
                    pass
    except Exception:
        pass



def run_pip_install_target():
    """Install requirements.txt into the local `lib` folder if missing packages are detected."""
    req = HERE.parent / "requirements.txt"
    if not req.exists():
        return False
    print('로컬 `lib`에 필요한 패키지가 없으므로 설치를 시도합니다. 이 작업은 시간이 걸립니다...')
    cmd = [sys.executable, '-m', 'pip', 'install', '--target', str(LIB_DIR), '-r', str(req)]
    try:
        subprocess.check_call(cmd)
        # ensure newly-installed packages are importable
        if str(LIB_DIR) not in sys.path:
            sys.path.insert(0, str(LIB_DIR))
        return True
    except subprocess.CalledProcessError as e:
        print('의존성 설치 실패:', e)
        return False


def find_cublas_dll():
    """Search common locations and PATH for cublas DLL (e.g., cublas64_12.dll)."""
    patterns = [
        os.path.join(os.environ.get('CUDA_PATH', ''), 'bin', 'cublas64_*.dll'),
        'C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/**/bin/cublas64_*.dll',
        'C:/Windows/System32/cublas64_*.dll',
    ]
    # search PATH
    for p in os.environ.get('PATH', '').split(os.pathsep):
        try:
            for f in glob.glob(os.path.join(p, 'cublas64_*.dll')):
                return f
        except Exception:
            pass

    for pat in patterns:
        try:
            hits = glob.glob(pat, recursive=True)
            if hits:
                return hits[0]
        except Exception:
            pass
    return None


def ensure_dependencies_and_check_cuda():
    """Ensure Python deps are available (install into lib if needed) and return whether CUDA runtime exists."""
    need_install = False
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        need_install = True

    try:
        import ctranslate2  # noqa: F401
    except Exception:
        need_install = True

    if need_install:
        ok = run_pip_install_target()
        if not ok:
            print('로컬 의존성 설치에 실패했습니다. 계속하려면 수동으로 설치하거나 CPU모드로 실행하세요.')

    # check cublas
    cublas = find_cublas_dll()
    if cublas:
        print('cublas 라이브러리 발견:', cublas)
        return True
    else:
        print('cublas 라이브러리를 찾지 못했습니다 — GPU 사용 불가(자동 CPU 폴백).')
        return False


def use_external_runtime(runtime_root: str):
    """Configure environment to use an external runtime folder that includes Python and packages.
    This will prepend runtime's site-packages to sys.path and add runtime bin/libs to PATH.
    """
    rt = Path(runtime_root)
    if not rt.exists():
        return False
    site_pkgs = rt / 'Lib' / 'site-packages'
    if site_pkgs.exists():
        sys.path.insert(0, str(site_pkgs))
        print('외부 런타임 site-packages 추가:', site_pkgs)

        # Also set PYTHONPATH so child processes spawned with 'spawn' inherit the runtime's
        # site-packages path (Windows multiprocessing spawn doesn't inherit runtime sys.path).
        existing = os.environ.get('PYTHONPATH', '')
        new_py = str(site_pkgs) + (os.pathsep + existing if existing else '')
        os.environ['PYTHONPATH'] = new_py
        # If torch is present, add its internal lib directory to PATH so DLLs like cublas are found
        torch_lib = site_pkgs / 'torch' / 'lib'
        if torch_lib.exists():
            # Prepend to PATH for DLL resolution
            old_path = os.environ.get('PATH', '')
            os.environ['PATH'] = str(torch_lib) + os.pathsep + old_path
            print('외부 런타임의 torch lib 경로를 PATH에 추가:', torch_lib)

    # Add runtime root and libs/bin to PATH for DLL resolution
    candidates = [str(rt), str(rt / 'libs'), str(rt / 'bin'), str(rt / 'Lib'), str(rt / 'Scripts')]
    old_path = os.environ.get('PATH', '')
    new_path = os.pathsep.join([p for p in candidates if Path(p).exists()]) + os.pathsep + old_path
    os.environ['PATH'] = new_path
    print('외부 런타임 PATH에 추가됨:', candidates)
    return True


def detect_and_use_known_runtime(cli_runtime: str = None):
    # If CLI provided runtime path, try it first
    if cli_runtime:
        if use_external_runtime(cli_runtime):
            return True

    # Look for GPT-SoVITS runtime in user's Downloads (common location from attachment)
    downloads = Path.home() / 'Downloads'
    try:
        for p in downloads.glob('**/GPT-SoVITS*'):
            rt = p / 'runtime'
            if rt.exists():
                print('GPT-SoVITS 런타임 자동 감지:', rt)
                return use_external_runtime(str(rt))
    except Exception:
        pass

    # Look near this script for any runtime folder
    try:
        for p in HERE.parent.glob('**/runtime'):
            # ignore our own lib/runtime if any
            if p.exists():
                print('로컬 런타임 감지:', p)
                return use_external_runtime(str(p))
    except Exception:
        pass

    return False


MODEL = None


def init_model(model_size, device, compute_type):
    # initializer for worker processes
    global MODEL
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        print("모듈 `faster_whisper` 를 불러올 수 없습니다. lib 폴더에 설치했는지 확인하세요.")
        raise
    try:
        if compute_type:
            MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
        else:
            MODEL = WhisperModel(model_size, device=device)
    except TypeError as e:
        # Some ctranslate2 builds (or environments) may not accept cuda/device kwargs on Windows.
        print(f"WhisperModel 초기화 중 TypeError 발생: {e}")
        if device == 'cuda':
            print('GPU 초기화 실패 — CPU로 폴백하여 모델을 로드합니다.')
            MODEL = WhisperModel(model_size, device='cpu', compute_type=compute_type)
        else:
            raise


def transcribe_file(path):
    """Worker: transcribe one wav file and return serializable result."""
    global MODEL
    try:
        from faster_whisper import WhisperModel
        # MODEL should be initialized by initializer
        if MODEL is None:
            # fallback: create model in this process (rare)
            MODEL = WhisperModel("small", device="cpu")

        segments, info = MODEL.transcribe(str(path), beam_size=5)
        segs = []
        for s in segments:
            segs.append({
                "start": float(s.start),
                "end": float(s.end),
                "text": s.text.strip()
            })
        language = getattr(info, "language", "") or ""
        # classify: if any word-like characters in transcript -> Voice
        import re
        combined_text = " ".join(s["text"] for s in segs).strip()
        classification = "Voice" if re.search(r"\w", combined_text) else "SFX"
        return {
            "path": str(path),
            "segments": segs,
            "language": language,
            "classification": classification,
            "subtitles": combined_text,
        }
    except Exception as e:
        return {"path": str(path), "error": traceback.format_exc()}


def format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h = ms // 3600000
    ms -= h * 3600000
    m = ms // 60000
    ms -= m * 60000
    s = ms // 1000
    ms -= s * 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_srt(segments):
    lines = []
    for i, s in enumerate(segments, start=1):
        start = format_timestamp(s["start"]) 
        end = format_timestamp(s["end"]) 
        text = s["text"].replace('\r', '').strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def find_wavs(input_dir):
    for root, dirs, files in os.walk(input_dir):
        for f in files:
            if f.lower().endswith('.wav'):
                yield Path(root) / f


def write_tsv_line(tsv_path, row):
    # row: list of 5 columns
    with open(tsv_path, 'a', encoding='utf-8') as fh:
        fh.write('\t'.join(row) + '\n')


def safe_text_for_tsv(text: str) -> str:
    return text.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', default='input', help='input folder (recursive)')
    parser.add_argument('--tsv', '-o', default='results.tsv', help='output TSV path')
    parser.add_argument('--model', default='small', help='whisper model size (tiny, base, small, medium, large)')
    parser.add_argument('--device', default='cpu', choices=['cpu', 'cuda'], help='device to run model on')
    parser.add_argument('--runtime', default=None, help='path to external runtime folder to use (adds its site-packages and DLL paths)')
    parser.add_argument('--compute_type', default=None, help='compute_type passed to faster-whisper (e.g., int8_float16)')
    parser.add_argument('--workers', type=int, default=0, help='number of worker processes (default: cpu_count-1)')
    args = parser.parse_args()

    # detect/use external runtime (e.g., GPT-SoVITS runtime) before ensuring deps
    if detect_and_use_known_runtime(args.runtime):
        print('외부 런타임 구성 완료 - 해당 런타임의 패키지 및 DLL을 사용합니다.')

    # ensure deps and check for CUDA runtime first
    has_cublas = ensure_dependencies_and_check_cuda()

    # if requested cuda but no runtime, fallback to cpu
    if args.device == 'cuda' and not has_cublas:
        print('CUDA 런타임을 찾을 수 없어 자동으로 CPU로 폴백합니다.')
        args.device = 'cpu'

    input_dir = Path(args.input)
    if not input_dir.exists():
        print('입력 폴더가 없습니다:', input_dir)
        return

    tsv_path = Path(args.tsv)
    # create header if not exists
    if not tsv_path.exists():
        with open(tsv_path, 'w', encoding='utf-8') as fh:
            fh.write('파일명\t상대경로\t분류\t언어\t자막\n')

    cpu_count = max(1, multiprocessing.cpu_count() - 1)
    workers = args.workers or cpu_count
    if args.device == 'cuda' and workers > 1:
        # recommend single worker for GPU to avoid contention, but allow user override
        print('GPU 사용시 멀티프로세스는 메모리/장치 경쟁이 발생할 수 있습니다. 자동으로 worker=1로 설정합니다.')
        workers = 1

    print(f'작업 스레드(프로세스) 수: {workers}')

    files = list(find_wavs(input_dir))
    if not files:
        print('처리할 wav 파일이 없습니다.')
        return

    # Filter out files that already have corresponding .srt -> skip
    to_process = []
    for p in files:
        srt_path = p.with_suffix('.srt')
        if srt_path.exists():
            print('이미 처리되어 스킵:', p)
            continue
        to_process.append(p)

    if not to_process:
        print('처리할 새 파일이 없습니다.')
        return

    # Start process pool
    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=init_model, initargs=(args.model, args.device, args.compute_type)) as exe:
            futures = {exe.submit(transcribe_file, p): p for p in to_process}
            try:
                for fut in as_completed(futures):
                    src_path = futures[fut]
                    try:
                        res = fut.result()
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        print('작업 중 오류:', src_path, e)
                        continue

                    if 'error' in res:
                        print('파일 처리 실패:', src_path)
                        print(res['error'])
                        continue

                    rel = os.path.relpath(res['path'], start=str(input_dir))
                    filename = os.path.basename(res['path'])

                    if res['classification'] == 'Voice' and res['subtitles']:
                        srt_text = make_srt(res['segments'])
                        srt_path = Path(res['path']).with_suffix('.srt')
                        with open(srt_path, 'w', encoding='utf-8') as fh:
                            fh.write(srt_text)
                        language = res.get('language', '')
                        subtitles = safe_text_for_tsv(res['subtitles'])
                    else:
                        language = ''
                        subtitles = ''

                    row = [filename, rel.replace('\\', '/'), res['classification'], language, subtitles]
                    write_tsv_line(tsv_path, row)
                    print('완료:', rel)
            except KeyboardInterrupt:
                print('\n중단 요청 감지: 진행 중인 작업을 취소합니다...')
                # Attempt to cancel running futures and shutdown pool
                exe.shutdown(wait=False, cancel_futures=True)
                print('모든 워커에 중단 신호를 보냈습니다.')
    except KeyboardInterrupt:
        print('메인에서 중단되었습니다.')


if __name__ == '__main__':
    print('작업 시작')
    main()
    print('작업 종료')

import os
import sys
from pathlib import Path
from task_runner import TaskProcess

ROOT = Path(__file__).resolve().parents[1]

_runner = TaskProcess('convert')


def start_convert(input_dir='input', site_packages=None, workers=1, overwrite=False, runtime=None):
    runtime_python = ROOT / runtime / 'python.exe' if runtime else Path(sys.executable)
    if runtime and not runtime_python.exists():
        runtime_python = Path(sys.executable)

    cmd = [str(runtime_python), str(ROOT / 'app' / 'convert_wem.py'),
           '--input', str(input_dir), '--site-packages', str(site_packages or os.path.join('runtime', 'Lib', 'site-packages')),
           '--workers', str(workers)]
    if overwrite:
        cmd.append('--overwrite')

    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return _runner.start(cmd, str(ROOT), env=env)


def get_status():
    return _runner.get_status()


def stop_convert():
    return _runner.stop()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='input')
    parser.add_argument('--site-packages', default=os.path.join('runtime', 'Lib', 'site-packages'))
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--runtime', default=None)
    args = parser.parse_args()
    start_convert(args.input, args.site_packages, args.workers, args.overwrite, args.runtime)

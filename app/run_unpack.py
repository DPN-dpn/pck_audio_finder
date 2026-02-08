import os
import sys
from pathlib import Path
from task_runner import TaskProcess

ROOT = Path(__file__).resolve().parents[1]

_runner = TaskProcess('unpack')



def start_unpack(input_dir='input', out_base='unpacked', runtime=None, workers=0):
    runtime_python = ROOT / runtime / 'python.exe' if runtime else Path(sys.executable)
    if runtime and not runtime_python.exists():
        runtime_python = Path(sys.executable)

    cmd = [str(runtime_python), str(ROOT / 'app' / 'unpack_pck.py'),
           '--input', str(input_dir), '--output', str(out_base), '--workers', str(workers)]

    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return _runner.start(cmd, str(ROOT), env=env)


def get_status():
    return _runner.get_status()


def stop_unpack():
    return _runner.stop()


if __name__ == '__main__':
    # simple CLI for debugging
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='input')
    parser.add_argument('--output', default='unpacked')
    parser.add_argument('--runtime', default=None)
    parser.add_argument('--workers', type=int, default=0)
    args = parser.parse_args()
    start_unpack(args.input, args.output, args.runtime, args.workers)

import os
import sys
from pathlib import Path
from task_runner import TaskProcess

ROOT = Path(__file__).resolve().parents[1]

_runner = TaskProcess('transcription')



def start_transcription(input_dir='input', tsv='results.tsv', model='small', device='cpu', runtime='runtime'):
    runtime_python = ROOT / runtime / 'python.exe'
    if not runtime_python.exists():
        runtime_python = Path(sys.executable)

    cmd = [str(runtime_python), str(ROOT / 'app' / 'transcribe.py'),
           '--input', str(input_dir), '--tsv', str(tsv),
           '--model', model, '--device', device, '--runtime', runtime]

    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['TRANSCRIBE_SKIP_CHILD_LOG'] = '1'
    return _runner.start(cmd, str(ROOT), env=env)


def get_status():
    return _runner.get_status()


def stop_transcription():
    return _runner.stop()

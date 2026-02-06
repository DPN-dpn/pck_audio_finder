from flask import Flask, render_template, request, jsonify, Response
from pathlib import Path
import threading
import sys
import os
# Ensure this `app` directory is on sys.path so local imports work when running
# the script as `python app\main.py` from the project root or elsewhere.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from run_transcription import start_transcription, get_status as get_status_transcribe, stop_transcription, LOG_FILE as LOG_FILE_TRANSCRIBE
from run_unpack import start_unpack, get_status as get_status_unpack, stop_unpack, LOG_FILE as LOG_FILE_UNPACK
from run_convert import start_convert, get_status as get_status_convert, stop_convert, LOG_FILE as LOG_FILE_CONVERT

app = Flask(__name__, template_folder='../web', static_folder='static')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start', methods=['POST'])
def start():
    data = request.json or request.form
    task = (data.get('task') if isinstance(data, dict) else None) or request.args.get('task') or 'transcribe'
    input_dir = data.get('input', 'input')
    model = data.get('model', 'small')
    device = data.get('device', 'cpu')
    runtime = data.get('runtime', 'runtime')
    tsv = data.get('tsv', 'results.tsv')
    # task routing
    if task == 'unpack':
        out_base = data.get('output', 'unpacked')
        workers = int(data.get('workers') or 0)
        ok = start_unpack(input_dir, out_base, runtime, workers)
        status = get_status_unpack()
    elif task == 'convert':
        site_packages = data.get('site-packages') or data.get('site_packages') or os.path.join('runtime', 'Lib', 'site-packages')
        workers = int(data.get('workers') or 1)
        overwrite = bool(data.get('overwrite'))
        ok = start_convert(input_dir, site_packages, workers, overwrite, runtime)
        status = get_status_convert()
    else:
        ok = start_transcription(input_dir, tsv, model, device, runtime)
        status = get_status_transcribe()
    return jsonify({'started': bool(ok), 'log': status.get('log', '')})


@app.route('/status')
def status():
    task = request.args.get('task') or 'transcribe'
    if task == 'unpack':
        return jsonify(get_status_unpack())
    if task == 'convert':
        return jsonify(get_status_convert())
    return jsonify(get_status_transcribe())


@app.route('/stop', methods=['POST'])
def stop():
    data = request.json or request.form
    task = (data.get('task') if isinstance(data, dict) else None) or request.args.get('task') or 'transcribe'
    if task == 'unpack':
        stopped = stop_unpack()
        status = get_status_unpack()
    elif task == 'convert':
        stopped = stop_convert()
        status = get_status_convert()
    else:
        stopped = stop_transcription()
        status = get_status_transcribe()
    return jsonify({'stopped': bool(stopped), 'log': status.get('log', '')})


@app.route('/logs/stream')
def stream_logs():
    def generate():
        import time
        last_pos = 0
        first_seen = False
        # If file not exist yet, wait until it appears
        while True:
            try:
                # choose log file based on query param
                from urllib.parse import urlparse, parse_qs
                q = urlparse(request.environ.get('RAW_URI', request.environ.get('REQUEST_URI', ''))).query
                task = parse_qs(q).get('task', ['transcribe'])[0]
                use_log = LOG_FILE_TRANSCRIBE
                if task == 'unpack':
                    use_log = LOG_FILE_UNPACK
                elif task == 'convert':
                    use_log = LOG_FILE_CONVERT

                if use_log.exists():
                    size = use_log.stat().st_size
                    if size < last_pos:
                        last_pos = 0
                    with open(use_log, 'rb') as f:
                        if not first_seen:
                            f.seek(0, 2)
                            last_pos = f.tell()
                            first_seen = True
                        else:
                            f.seek(last_pos)

                        data = f.read()
                        last_pos = f.tell()
                        if data:
                            text = None
                            try:
                                text = data.decode('utf-8')
                            except Exception:
                                try:
                                    text = data.decode('cp949')
                                except Exception:
                                    try:
                                        text = data.decode('euc-kr')
                                    except Exception:
                                        text = data.decode('latin1', errors='replace')

                            for ln in text.splitlines(True):
                                yield f"data: {ln.rstrip()}\n\n"
                time.sleep(0.5)
            except GeneratorExit:
                break
            except Exception:
                time.sleep(0.5)
    # Ensure charset in header so browsers interpret bytes as UTF-8
    headers = {'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache'}
    return Response(generate(), headers=headers)


if __name__ == '__main__':
    # Use threaded server for simplicity; runs on localhost only
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)

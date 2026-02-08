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
from run_transcription import start_transcription, get_status as get_status_transcribe, stop_transcription
from run_unpack import start_unpack, get_status as get_status_unpack, stop_unpack
from run_convert import start_convert, get_status as get_status_convert, stop_convert
import logging_helper as lg

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
    # stream_logs does not require a per-task log file selection anymore

    def generate():
        import time
        # On connect, send entire current log so client has context, then
        # afterwards send only the newly appended portion using a file offset.
        try:
            # initial full content
            full = lg.read_all()
            if full:
                for ln in full.splitlines(True):
                    yield f"data: {ln.rstrip()}\n\n"

            # track current file offset (in bytes)
            try:
                pos = lg.LOG_FILE.stat().st_size if lg.LOG_FILE.exists() else 0
            except Exception:
                pos = 0

            # Wait for notifications from logging_helper and then send only the
            # newly appended bytes decoded via `read_from`.
            while True:
                got = lg.wait_notification(timeout=0.5)
                if not got:
                    continue
                try:
                    chunk, pos = lg.read_from(pos)
                except Exception:
                    chunk = ''
                if chunk:
                    for ln in chunk.splitlines(True):
                        yield f"data: {ln.rstrip()}\n\n"
        except GeneratorExit:
            return
        except Exception:
            return
    # Ensure charset in header so browsers interpret bytes as UTF-8
    headers = {'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache'}
    return Response(generate(), headers=headers)


@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if callable(func):
        try:
            func()
            return jsonify({'shutdown': True})
        except Exception:
            # If Werkzeug shutdown fails, fall back to os._exit()
            pass

    # Fallback: exit in a background thread to avoid blocking the request
    threading.Thread(target=lambda: os._exit(0), daemon=True).start()
    return jsonify({'shutdown': True})


if __name__ == '__main__':
    # Use threaded server for simplicity; runs on localhost only
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)

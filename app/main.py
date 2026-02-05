from flask import Flask, render_template, request, jsonify, Response
from pathlib import Path
import threading
import sys
# Ensure this `app` directory is on sys.path so local imports work when running
# the script as `python app\main.py` from the project root or elsewhere.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from run_transcription import start_transcription, get_status, stop_transcription, LOG_FILE

app = Flask(__name__, template_folder='../web', static_folder='static')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start', methods=['POST'])
def start():
    data = request.json or request.form
    input_dir = data.get('input', 'input')
    model = data.get('model', 'small')
    device = data.get('device', 'cpu')
    runtime = data.get('runtime', 'runtime')
    tsv = data.get('tsv', 'results.tsv')
    ok = start_transcription(input_dir, tsv, model, device, runtime)
    # Return current log snapshot so client can clear its view immediately
    status = get_status()
    return jsonify({'started': bool(ok), 'log': status.get('log', '')})


@app.route('/status')
def status():
    return jsonify(get_status())


@app.route('/stop', methods=['POST'])
def stop():
    stopped = stop_transcription()
    status = get_status()
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
                if LOG_FILE.exists():
                    size = LOG_FILE.stat().st_size
                    # If file was truncated (e.g., start cleared it), reset last_pos so
                    # the new contents are delivered.
                    if size < last_pos:
                        last_pos = 0
                    with open(LOG_FILE, 'rb') as f:
                        if not first_seen:
                            # On first observation, skip existing contents so clients
                            # that already fetched a snapshot don't get duplicates.
                            f.seek(0, 2)
                            last_pos = f.tell()
                            first_seen = True
                        else:
                            f.seek(last_pos)

                        data = f.read()
                        last_pos = f.tell()
                        if data:
                            # Try decoding as UTF-8 first; if that fails, try common Windows encodings
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
                                        # last resort: latin1 to preserve bytes
                                        text = data.decode('latin1', errors='replace')

                            # send each line as an SSE data event
                            for ln in text.splitlines(True):
                                # Replace lone CR with LF and strip trailing newlines for clean SSE
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

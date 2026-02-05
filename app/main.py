from flask import Flask, render_template, request, jsonify
from pathlib import Path
import threading
import sys
# Ensure this `app` directory is on sys.path so local imports work when running
# the script as `python app\main.py` from the project root or elsewhere.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from run_transcription import start_transcription, get_status, stop_transcription

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
    return jsonify({'started': bool(ok)})


@app.route('/status')
def status():
    return jsonify(get_status())


@app.route('/stop', methods=['POST'])
def stop():
    stopped = stop_transcription()
    return jsonify({'stopped': bool(stopped)})


if __name__ == '__main__':
    # Use threaded server for simplicity; runs on localhost only
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)

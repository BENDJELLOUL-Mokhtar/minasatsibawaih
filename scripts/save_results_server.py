#!/usr/bin/env python3
"""
save_results_server.py
A tiny Flask server to accept saving student results or entire state.
Usage:
  python save_results_server.py         # runs server on 127.0.0.1:5000
  python save_results_server.py --test  # run a self-test (POST sample payload then exit)

Endpoints:
  POST /api/save_result  -> accept JSON payload for a single result and append to scripts/results/results.json
  POST /api/save_state   -> accept JSON payload {state: ...} and save to scripts/results/last_state.json
  GET  /api/results      -> return list of saved results

This is intended as a local development helper only.
"""
import os
import json
import argparse
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)
ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(ROOT, 'results')
RESULTS_FILE = os.path.join(RESULTS_DIR, 'results.json')
LAST_STATE = os.path.join(RESULTS_DIR, 'last_state.json')

os.makedirs(RESULTS_DIR, exist_ok=True)
if not os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)


def load_results():
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_results(lst):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)


@app.route('/api/save_result', methods=['POST'])
def save_result():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({'error':'no json payload'}), 400
        lst = load_results()
        payload['_saved_at'] = datetime.utcnow().isoformat() + 'Z'
        lst.append(payload)
        save_results(lst)
        return jsonify({'ok': True, 'count': len(lst)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/save_state', methods=['POST'])
def save_state():
    try:
        payload = request.get_json()
        if not payload or 'state' not in payload:
            return jsonify({'error':'missing state'}), 400
        with open(LAST_STATE, 'w', encoding='utf-8') as f:
            json.dump(payload['state'], f, ensure_ascii=False, indent=2)
        return jsonify({'ok': True, 'saved': LAST_STATE})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/results', methods=['GET'])
def api_results():
    try:
        return jsonify(load_results())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--test', action='store_true', help='Run self-test and exit')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=5000)
    args = p.parse_args()
    if args.test:
        # Run a quick self-test using Flask test client
        with app.test_client() as c:
            sample = {'student_id':'s_test','module':'UD_IMPORT:0','score':3,'max':4,'time':datetime.utcnow().isoformat()}
            r = c.post('/api/save_result', json=sample)
            print('POST /api/save_result ->', r.status_code, r.get_json())
            r2 = c.get('/api/results')
            print('GET /api/results ->', r2.status_code, 'count=', len(r2.get_json()))
        print('Self-test completed.')
    else:
        print(f'Starting server on http://{args.host}:{args.port} (data -> {RESULTS_DIR})')
        app.run(host=args.host, port=args.port)

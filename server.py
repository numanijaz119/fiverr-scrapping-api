import os
import sys
import json
import time
import glob
import threading
import subprocess
import webbrowser
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GIGS_DIR = os.path.join(BASE_DIR, 'gigs_data')
ANALYSIS_DIR = os.path.join(BASE_DIR, 'keyword_analysis')
ENV_FILE = os.path.join(BASE_DIR, '.env')

# Global job state
job = {
    'running': False,
    'logs': [],
    'done': True,
    'process': None,
}
job_lock = threading.Lock()


def add_log(entry):
    with job_lock:
        job['logs'].append(entry)


_SCRAPER_ERROR_SUBTYPES = {
    'INVALID_KEY':    ('error',   'invalid_key'),
    'QUOTA_EXCEEDED': ('error',   'quota_exceeded'),
    'API_ERROR':      ('error',   'api_error'),
    'NO_GIGS_FOUND':  ('warning', 'no_gigs_found'),
}


def _classify_line(raw_line):
    """
    Return a log entry dict for a raw output line.
    Lines starting with SCRAPER_ERROR:<SUBTYPE>:<message> become alert events.
    All other lines are plain log entries.
    """
    line = raw_line.rstrip()
    if line.startswith('SCRAPER_ERROR:'):
        parts = line.split(':', 2)          # ['SCRAPER_ERROR', 'SUBTYPE', 'message']
        subtype_key = parts[1] if len(parts) > 1 else 'API_ERROR'
        message     = parts[2] if len(parts) > 2 else line
        log_type, subtype = _SCRAPER_ERROR_SUBTYPES.get(subtype_key, ('error', 'api_error'))
        return {'type': 'alert', 'subtype': subtype, 'level': log_type, 'data': message}
    return {'type': 'log', 'data': line}


def run_process(cmd, on_done):
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    unbuffered_cmd = [cmd[0], '-u'] + cmd[1:]
    try:
        proc = subprocess.Popen(
            unbuffered_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1,
            cwd=BASE_DIR,
            env=env,
        )
        with job_lock:
            job['process'] = proc

        for line in proc.stdout:
            add_log(_classify_line(line))

        proc.wait()
        on_done(proc.returncode == 0, proc.returncode)
    except Exception as e:
        add_log({'type': 'error', 'data': str(e)})
        on_done(False, -1)
    finally:
        with job_lock:
            job['running'] = False
            job['done'] = True


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/keywords')
def get_keywords():
    keywords = []
    if os.path.exists(GIGS_DIR):
        for d in sorted(os.listdir(GIGS_DIR)):
            full = os.path.join(GIGS_DIR, d)
            if os.path.isdir(full):
                count = len(glob.glob(os.path.join(full, '*.json')))
                keywords.append({'name': d, 'count': count})
    return jsonify(keywords)


@app.route('/api/config', methods=['GET'])
def get_config():
    key = ''
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith('SCRAPER_API_KEY='):
                    key = line.strip().split('=', 1)[1]
    return jsonify({'api_key': key})


@app.route('/api/config', methods=['POST'])
def save_config():
    api_key = request.json.get('api_key', '').strip()
    with open(ENV_FILE, 'w') as f:
        f.write(f'SCRAPER_API_KEY={api_key}\n')
    return jsonify({'success': True})


@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    with job_lock:
        if job['running']:
            return jsonify({'error': 'A job is already running'}), 400
        keyword = request.json.get('keyword', '').strip()
        pages = int(request.json.get('pages', 1))
        if not keyword:
            return jsonify({'error': 'Keyword is required'}), 400
        job['running'] = True
        job['done'] = False
        job['logs'] = []
        job['process'] = None

    add_log({'type': 'info', 'data': f'Starting scrape: "{keyword}" ({pages} page(s))'})

    cmd = [sys.executable, 'Fiverr_search-Scrapper.py', keyword, '--pages', str(pages)]

    def on_done(success, code):
        if success:
            add_log({'type': 'success', 'data': 'Scraping completed successfully!'})
            add_log({'type': 'result', 'data': os.path.join(GIGS_DIR, keyword)})
        else:
            add_log({'type': 'error', 'data': f'Scraping failed (exit code {code})'})

    threading.Thread(target=run_process, args=(cmd, on_done), daemon=True).start()
    return jsonify({'success': True})


@app.route('/api/scrape-category', methods=['POST'])
def start_scrape_category():
    with job_lock:
        if job['running']:
            return jsonify({'error': 'A job is already running'}), 400
        url   = request.json.get('url', '').strip()
        pages = int(request.json.get('pages', 1))
        if not url:
            return jsonify({'error': 'Category URL is required'}), 400
        if 'fiverr.com/categories/' not in url:
            return jsonify({'error': 'URL must be a Fiverr category URL'}), 400
        job['running'] = True
        job['done']    = False
        job['logs']    = []
        job['process'] = None

    add_log({'type': 'info', 'data': f'Starting category scrape: {url} ({pages} page(s))'})

    cmd = [sys.executable, 'Fiverr_category-Scrapper.py', url, '--pages', str(pages)]

    def on_done(success, code):
        if success:
            add_log({'type': 'success', 'data': 'Category scraping completed successfully!'})
            add_log({'type': 'result',  'data': GIGS_DIR})
        else:
            add_log({'type': 'error', 'data': f'Scraping failed (exit code {code})'})

    threading.Thread(target=run_process, args=(cmd, on_done), daemon=True).start()
    return jsonify({'success': True})


@app.route('/api/extract', methods=['POST'])
def start_extract():
    with job_lock:
        if job['running']:
            return jsonify({'error': 'A job is already running'}), 400
        extract_type = request.json.get('type', '').strip()   # 'keywords' or 'packages'
        keyword      = request.json.get('keyword', '').strip()
        if not keyword:
            return jsonify({'error': 'Keyword is required'}), 400
        if extract_type not in ('keywords', 'packages'):
            return jsonify({'error': 'Invalid extract type'}), 400

        analysis_file = os.path.join(ANALYSIS_DIR, f'{keyword}_analysis.json')
        if not os.path.exists(analysis_file):
            return jsonify({'error': f'No analysis file found for "{keyword}". Run Analyze first.'}), 400

        job['running'] = True
        job['done']    = False
        job['logs']    = []
        job['process'] = None

    script     = 'extract_keywords.py' if extract_type == 'keywords' else 'extract_packages.py'
    suffix     = '_keywords.txt' if extract_type == 'keywords' else '_packages.txt'
    output_file = os.path.join(ANALYSIS_DIR, f'{keyword}_analysis{suffix}')
    label      = 'Keywords' if extract_type == 'keywords' else 'Packages'

    add_log({'type': 'info', 'data': f'Extracting {label} for: "{keyword}"'})

    cmd = [sys.executable, script, analysis_file, '--output', output_file]

    def on_done(success, code):
        if success:
            add_log({'type': 'success', 'data': f'{label} extraction complete!'})
            add_log({'type': 'result',  'data': output_file})
        else:
            add_log({'type': 'error', 'data': f'Extraction failed (exit code {code})'})

    threading.Thread(target=run_process, args=(cmd, on_done), daemon=True).start()
    return jsonify({'success': True})


@app.route('/api/analyze', methods=['POST'])
def start_analyze():
    with job_lock:
        if job['running']:
            return jsonify({'error': 'A job is already running'}), 400
        keyword = request.json.get('keyword', '').strip()
        if not keyword:
            return jsonify({'error': 'Keyword is required'}), 400
        keyword_dir = os.path.join(GIGS_DIR, keyword)
        if not os.path.exists(keyword_dir):
            return jsonify({'error': f'No scraped data found for "{keyword}"'}), 400
        job['running'] = True
        job['done'] = False
        job['logs'] = []
        job['process'] = None

    output_path = os.path.join(ANALYSIS_DIR, f'{keyword}_analysis.json')
    add_log({'type': 'info', 'data': f'Analyzing keyword: "{keyword}"'})

    cmd = [sys.executable, 'analyze_keyword.py', keyword_dir]

    def on_done(success, code):
        if success:
            add_log({'type': 'success', 'data': 'Analysis complete!'})
            add_log({'type': 'result', 'data': output_path})
        else:
            add_log({'type': 'error', 'data': f'Analysis failed (exit code {code})'})

    threading.Thread(target=run_process, args=(cmd, on_done), daemon=True).start()
    return jsonify({'success': True})


@app.route('/api/logs/stream')
def logs_stream():
    def generate():
        idx = 0
        while True:
            with job_lock:
                snapshot = list(job['logs'])
                done = job['done']

            while idx < len(snapshot):
                yield f"data: {json.dumps(snapshot[idx])}\n\n"
                idx += 1

            if done and idx >= len(snapshot):
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
                break

            time.sleep(0.08)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/api/stop', methods=['POST'])
def stop_job():
    with job_lock:
        proc = job['process']
    if proc:
        proc.terminate()
        add_log({'type': 'warning', 'data': 'Job stopped by user.'})
    return jsonify({'success': True})


@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    path = request.json.get('path', '')
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    # On Windows (local), open in Explorer
    if os.name == 'nt':
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if os.path.exists(target):
            os.startfile(target)
            return jsonify({'success': True, 'local': True})
        return jsonify({'error': f'Path not found: {target}'}), 404
    # On server (Linux), return a download URL instead
    if os.path.isfile(path):
        rel = os.path.relpath(path, BASE_DIR)
        return jsonify({'success': True, 'local': False, 'download_url': f'/api/download?path={rel}'})
    return jsonify({'error': 'Open folder not supported on this platform'}), 400


@app.route('/api/download')
def download_file():
    from flask import send_file
    rel_path = request.args.get('path', '')
    full_path = os.path.join(BASE_DIR, rel_path)
    if os.path.isfile(full_path) and full_path.startswith(BASE_DIR):
        return send_file(full_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/status')
def status():
    with job_lock:
        return jsonify({'running': job['running']})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_local = port == 5000
    if is_local:
        threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    print(f'\n  Fiverr Scraper UI → http://localhost:{port}\n  Press Ctrl+C to stop.\n')
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

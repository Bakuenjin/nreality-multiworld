"""HTTP bridge between the Ruffle page/SWF and a backend. Standard library only.

The SWF polls POST /api/sync once per second via AVM1 LoadVars (urlencoded).
A backend provides snapshot(), sync(values), log(after), command(text) and receive(receipt, episode).
Game files provide swf, ruffle, state() and install(archive) (see gamefiles.GameFiles).
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

EPISODES = 200
LEVELS = 5
WEB = os.path.join(os.path.dirname(__file__), 'web')
MIME = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
        '.wasm': 'application/wasm', '.swf': 'application/x-shockwave-flash'}


def read_web(name):
    # The module loader reads from a plain folder as well as from inside a zipped .apworld.
    return __loader__.get_data(os.path.join(WEB, name))


def parse_checks(values):
    return {int(c) for c in values.get('checks', '').split(',') if c}


def validate_episode(episode):
    episode = int(episode)
    if not 0 <= episode < EPISODES:
        raise ValueError('Episode invalid')
    return episode


def join(numbers):
    return ','.join(map(str, sorted(numbers)))


class GameLink:
    """Last sync from the SWF, shared by all backends."""

    def __init__(self):
        self.game = None

    def seen(self, values):
        self.game = dict(lastSeen=time.time(), episode=values.get('episode'),
                         level=values.get('level'), mapCount=values.get('mapCount'))

    def snapshot(self):
        return dict(game=self.game, connected=bool(self.game and time.time() - self.game['lastSeen'] < 5))


class LocalState:
    """Offline test backend: items are simulated via the page, state is a JSON file."""
    mode = 'local'

    def __init__(self, path, session, starting=(0, 10, 20)):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.session = session
        self.data = dict(session=session, starting=list(starting), items={}, checks=[])
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
            if self.data['session'] != session:
                raise ValueError('State belongs to a different session')
        self.link = GameLink()

    def unlocked(self):
        return sorted(set(self.data['starting']) | set(self.data['items'].values()))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2) + '\n')
        os.replace(temp, self.path)

    def receive(self, receipt, episode):
        with self.lock:
            episode = validate_episode(episode)
            if not receipt or len(receipt) > 128:
                raise ValueError('Invalid receipt ID')
            previous = self.data['items'].get(receipt)
            if previous is not None and previous != episode:
                raise ValueError('Receipt ID already belongs to another item')
            self.data['items'][receipt] = episode
            self.save()

    def sync(self, values):
        with self.lock:
            if values.get('session') != self.session:
                raise ValueError('Wrong session')
            candidates = parse_checks(values)
            unlocked = self.unlocked()
            if any(not 0 <= c < EPISODES * LEVELS or c // LEVELS not in unlocked for c in candidates):
                raise ValueError('Invalid or locked check')
            checks = sorted(set(self.data['checks']) | candidates)
            if checks != self.data['checks']:
                self.data['checks'] = checks
                self.save()
            self.link.seen(values)
            return dict(session=self.session, unlocked=join(unlocked), checked=join(checks), episodes='')

    def log(self, after):
        return []

    def command(self, text):
        raise ValueError('Commands need a MultiworldGG connection')

    def snapshot(self):
        with self.lock:
            return dict(mode=self.mode, session=self.session, episodes=list(range(EPISODES)),
                        unlocked=self.unlocked(), checks=self.data['checks'], items=self.data['items'],
                        goal=None, server=None, **self.link.snapshot())


class StaticFiles:
    """A fixed SWF and Ruffle folder (development, local test mode, --game-dir)."""

    def __init__(self, swf, ruffle):
        self.swf, self.ruffle = Path(swf), Path(ruffle)

    def state(self):
        return dict(ready=True, busy=False, message='')

    def install(self, archive):
        raise ValueError('The game folder was given on the command line')


MAX_ARCHIVE = 64 * 1024 * 1024


def handler_for(backend, port, files):
    def state():
        return {**backend.snapshot(), 'files': files.state()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and str(args[0]).startswith(('POST /api/sync', 'GET /api/state')):
                return
            super().log_message(fmt, *args)

        def respond(self, body, status=200, mime='application/json'):
            if isinstance(body, dict):
                body = json.dumps(body).encode()
            if isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            path = url.path
            if path == '/api/state':
                self.respond(state())
                return
            if path == '/api/log':
                try:
                    after = int(parse_qs(url.query).get('after', ['0'])[0] or 0)
                except ValueError:
                    self.respond({'error': 'Invalid log position'}, 400)
                    return
                self.respond(dict(entries=backend.log(after)))
                return
            web = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}.get(path)
            if web:
                self.respond(read_web(web), mime=MIME[os.path.splitext(web)[1]])
                return
            file = files.swf if path == '/game.swf' else None
            if path.startswith('/ruffle/') and '%' not in path and '..' not in path:
                file = files.ruffle / path[len('/ruffle/'):]
            if not file or not file.is_file():
                self.respond({'error': 'Not found'}, 404)
                return
            self.respond(file.read_bytes(), mime=MIME.get(file.suffix, 'application/octet-stream'))

        def do_POST(self):
            if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{port}'):
                self.respond({'error': 'Invalid origin'}, 403)
                return
            if self.path == '/api/setup':
                self.install_game()
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 20000:
                    raise ValueError('Invalid body size')
                body = self.rfile.read(length).decode()
                if self.headers.get('Content-Type', '').startswith('application/json'):
                    values = json.loads(body)
                else:
                    values = {k: v[-1] for k, v in parse_qs(body, keep_blank_values=True).items()}
                if self.path == '/api/sync':
                    self.respond(urlencode(backend.sync(values)), mime='application/x-www-form-urlencoded')
                    return
                if self.path == '/api/item':
                    backend.receive(values['receipt'], values['episode'])
                elif self.path == '/api/command':
                    backend.command(str(values['text']))
                else:
                    self.respond({'error': 'Not found'}, 404)
                    return
                self.respond(state())
            except (ValueError, KeyError, TypeError) as error:
                self.respond({'error': str(error)}, 400)

        def install_game(self):
            """Receives the player's NReality6g2.zip and builds the game from it."""
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= MAX_ARCHIVE:
                    raise ValueError('Invalid archive size')
                files.install(self.rfile.read(length))
                self.respond(state())
            except ValueError as error:
                self.respond({'error': str(error)}, 400)
            except OSError as error:  # e.g. the Ruffle download failed
                self.respond({'error': str(error)}, 502)
    return Handler


def serve(backend, port, files):
    """Start the bridge in a daemon thread and return the server (call shutdown() to stop)."""
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(backend, port, files))
    threading.Thread(target=server.serve_forever, name='NReality bridge', daemon=True).start()
    return server

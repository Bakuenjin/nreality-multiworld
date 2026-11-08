"""Local HTTP server between the browser and the client. Standard library only.

The browser page polls GET /api/state and shows the console; the game (the SWF in Ruffle) posts its progress
to POST /api/sync once per second via AVM1 LoadVars, urlencoded. Every request is answered by a Backend:
the MultiworldGG client (context.MultiworldBackend) or the offline test mode (offline.OfflineBackend).
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlencode, urlsplit

EPISODES = 200
LEVELS = 5
PAGE_DIR = os.path.join(os.path.dirname(__file__), 'web')
PAGE_FILES = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
CONTENT_TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
                 '.wasm': 'application/wasm', '.swf': 'application/x-shockwave-flash'}
CONTENT_SECURITY_POLICY = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; "
                           "style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'")
MAX_BODY = 20000
MAX_ARCHIVE = 64 * 1024 * 1024


class Backend(Protocol):
    """Answers the page and the game. Methods raise ValueError for invalid requests (sent back as HTTP 400)."""
    mode: str  # "multiworld" or "local"

    def state(self) -> dict[str, Any]: ...
    def sync(self, values: dict[str, str]) -> dict[str, Any]: ...
    def log_entries(self, after: int) -> list[dict[str, Any]]: ...
    def command(self, text: str) -> None: ...
    def receive_test_item(self, receipt: str, episode: int) -> None: ...


class GameFileSource(Protocol):
    """The built SWF and the Ruffle folder (see gamefiles.GameFiles and gamefiles.FixedGameFiles)."""
    swf: Path
    ruffle: Path

    def state(self) -> dict[str, Any]: ...
    def install(self, archive: bytes) -> None: ...


def read_page_file(name: str) -> bytes:
    # The module loader reads from a plain folder as well as from inside a zipped .apworld.
    return __loader__.get_data(os.path.join(PAGE_DIR, name))


def parse_checks(values: dict[str, str]) -> set[int]:
    """Checks the game reports as a comma-separated list of episode * 5 + level."""
    return {int(check) for check in values.get('checks', '').split(',') if check}


def validate_episode(episode: Any) -> int:
    episode = int(episode)
    if not 0 <= episode < EPISODES:
        raise ValueError('Episode invalid')
    return episode


def join_numbers(numbers) -> str:
    return ','.join(map(str, sorted(numbers)))


class GameConnection:
    """When the game last synced and where it was, shared by all backends for the page's status line."""

    def __init__(self) -> None:
        self.last_sync: dict[str, Any] | None = None

    def record_sync(self, values: dict[str, str]) -> None:
        self.last_sync = dict(lastSeen=time.time(), episode=values.get('episode'), level=values.get('level'),
                              mapCount=values.get('mapCount'))

    def state(self) -> dict[str, Any]:
        connected = bool(self.last_sync and time.time() - self.last_sync['lastSeen'] < 5)
        return dict(game=self.last_sync, connected=connected)


def make_request_handler(backend: Backend, port: int, files: GameFileSource) -> type[BaseHTTPRequestHandler]:
    def page_state() -> dict[str, Any]:
        return {**backend.state(), 'files': files.state()}

    class RequestHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and str(args[0]).startswith(('POST /api/sync', 'GET /api/state')):
                return  # polled every second
            super().log_message(fmt, *args)

        def respond(self, body, status=200, content_type='application/json'):
            if isinstance(body, dict):
                body = json.dumps(body)
            if isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', CONTENT_SECURITY_POLICY)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/api/state':
                self.respond(page_state())
            elif url.path == '/api/log':
                try:
                    after = int(parse_qs(url.query).get('after', ['0'])[0] or 0)
                except ValueError:
                    self.respond({'error': 'Invalid log position'}, 400)
                    return
                self.respond(dict(entries=backend.log_entries(after)))
            elif url.path in PAGE_FILES:
                name = PAGE_FILES[url.path]
                self.respond(read_page_file(name), content_type=CONTENT_TYPES[os.path.splitext(name)[1]])
            else:
                self.send_game_file(url.path)

        def send_game_file(self, path):
            file = files.swf if path == '/game.swf' else None
            if path.startswith('/ruffle/') and '%' not in path and '..' not in path:
                file = files.ruffle / path[len('/ruffle/'):]
            if not file or not file.is_file():
                self.respond({'error': 'Not found'}, 404)
                return
            self.respond(file.read_bytes(), content_type=CONTENT_TYPES.get(file.suffix, 'application/octet-stream'))

        def do_POST(self):
            # Only the page itself may post; other websites in the same browser must not.
            if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{port}'):
                self.respond({'error': 'Invalid origin'}, 403)
                return
            if self.path == '/api/setup':
                self.receive_game_archive()
                return
            try:
                values = self.read_values()
                if self.path == '/api/sync':
                    self.respond(urlencode(backend.sync(values)), content_type='application/x-www-form-urlencoded')
                    return
                if self.path == '/api/item':
                    backend.receive_test_item(values['receipt'], values['episode'])
                elif self.path == '/api/command':
                    backend.command(str(values['text']))
                else:
                    self.respond({'error': 'Not found'}, 404)
                    return
                self.respond(page_state())
            except (ValueError, KeyError, TypeError) as error:
                self.respond({'error': str(error)}, 400)

        def read_values(self) -> dict[str, Any]:
            """JSON from the page, urlencoded from the game."""
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= MAX_BODY:
                raise ValueError('Invalid body size')
            body = self.rfile.read(length).decode()
            if self.headers.get('Content-Type', '').startswith('application/json'):
                return json.loads(body)
            return {key: value[-1] for key, value in parse_qs(body, keep_blank_values=True).items()}

        def receive_game_archive(self):
            """Receives the player's NReality6g2.zip and builds the game from it."""
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= MAX_ARCHIVE:
                    raise ValueError('Invalid archive size')
                files.install(self.rfile.read(length))
                self.respond(page_state())
            except ValueError as error:
                self.respond({'error': str(error)}, 400)
            except OSError as error:  # e.g. the Ruffle download failed
                self.respond({'error': str(error)}, 502)

    return RequestHandler


def serve(backend: Backend, port: int, files: GameFileSource) -> ThreadingHTTPServer:
    """Starts the server in a daemon thread and returns it (call shutdown() to stop)."""
    server = ThreadingHTTPServer(('127.0.0.1', port), make_request_handler(backend, port, files))
    threading.Thread(target=server.serve_forever, name='NReality bridge', daemon=True).start()
    return server

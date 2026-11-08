"""Offline test mode without MultiworldGG: simulated items, same page and SWF as the real client.

python3 tools/offline.py [--fixture] serves the development build from .local/mod at http://127.0.0.1:8766.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION = 'local-prototype-v1'

# The page server, offline backend and game files need only the standard library. They are imported as the
# package "client", so the apworld package itself (which needs MultiworldGG) is never loaded.
sys.path.insert(0, str(ROOT / 'apworld' / 'nreality'))
from client import bridge, gamefiles, offline  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--fixture', action='store_true', help='Isolated engine completion smoke test')
    args = parser.parse_args()
    session = 'smoke-fixture-v1' if args.fixture else SESSION
    backend = offline.OfflineBackend(ROOT / '.local/state' / (session + '.json'), session,
                                     starting=(199,) if args.fixture else (0, 10, 20))
    swf = ROOT / '.local/mod' / ('n_multiworld_fixture.swf' if args.fixture else 'n_multiworld.swf')
    files = gamefiles.FixedGameFiles(swf, ROOT / '.local/ruffle')
    handler = bridge.make_request_handler(backend, args.port, files)
    server = bridge.ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    print(f'Local multiworld test session: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()

"""Offline test mode without MultiworldGG: simulated items, same page and SWF as the real client."""
import argparse
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION = 'local-prototype-v1'

# Load the standard-library-only bridge without importing the apworld package (needs MultiworldGG).
_spec = importlib.util.spec_from_file_location('nreality_bridge', ROOT / 'apworld/nreality/client/bridge.py')
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--fixture', action='store_true', help='Isolated engine completion smoke test')
    args = parser.parse_args()
    session = 'smoke-fixture-v1' if args.fixture else SESSION
    state = bridge.LocalState(ROOT / '.local/state' / (session + '.json'), session,
                              starting=(199,) if args.fixture else (0, 10, 20))
    swf = ROOT / '.local/mod' / ('n_multiworld_fixture.swf' if args.fixture else 'n_multiworld.swf')
    handler = bridge.handler_for(state, args.port, bridge.StaticFiles(swf, ROOT / '.local/ruffle'))
    server = bridge.ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    print(f'Local multiworld test session: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()

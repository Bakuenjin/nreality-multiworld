import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from tools.bridge import SESSION, bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'state.json'
        self.state = bridge.LocalState(self.path, SESSION)

    def test_item_is_one_episode_and_idempotent(self):
        self.state.receive('item-0', 100)
        self.state.receive('item-0', 100)
        self.assertEqual(self.state.unlocked(), [0, 10, 20, 100])
        self.assertEqual(len(self.state.data['items']), 1)
        with self.assertRaises(ValueError): self.state.receive('item-0', 101)

    def test_checks_deduplicate_and_survive_restart(self):
        self.state.receive('item-0', 100)
        for _ in range(2):
            result = self.state.sync(dict(session=SESSION, checks='500,501,500,'))
        self.assertEqual(result['checked'], '500,501')
        restarted = bridge.LocalState(self.path, SESSION)
        self.assertEqual(restarted.data['checks'], [500, 501])
        self.assertEqual(restarted.unlocked(), [0, 10, 20, 100])
        self.assertNotIn(101, restarted.unlocked())

    def test_locked_invalid_and_wrong_session_checks_rejected_atomically(self):
        for checks in ('0,500', '-1', '1000', 'x'):
            with self.assertRaises(ValueError):
                self.state.sync(dict(session=SESSION, checks=checks))
        with self.assertRaises(ValueError): self.state.sync(dict(session='other', checks='0'))
        self.assertEqual(self.state.data['checks'], [])

    def test_sync_marks_game_connected(self):
        self.assertFalse(self.state.snapshot()['connected'])
        result = self.state.sync(dict(session=SESSION, episode='0', level='2', mapCount='200'))
        self.assertEqual(result['unlocked'], '0,10,20')
        snapshot = self.state.snapshot()
        self.assertTrue(snapshot['connected'])
        self.assertEqual(snapshot['game']['level'], '2')

    def test_local_mode_has_no_console(self):
        self.assertEqual(self.state.log(0), [])
        with self.assertRaises(ValueError): self.state.command('!hint')


class HttpTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        folder = Path(directory.name)
        (folder / 'game.swf').write_bytes(b'FWS')
        state = bridge.LocalState(folder / 'state.json', SESSION)
        self.server = bridge.ThreadingHTTPServer(('127.0.0.1', 0), None)
        port = self.server.server_address[1]
        self.server.RequestHandlerClass = bridge.handler_for(state, port, bridge.StaticFiles(folder / 'game.swf', folder))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{port}'

    def request(self, path, data=None, headers={}):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url + path, data, headers)) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def test_routes(self):
        status, body = self.request('/api/state')
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['files']['ready'])
        self.assertEqual(self.request('/game.swf'), (200, b'FWS'))
        self.assertEqual(self.request('/api/log?after=x')[0], 400)
        self.assertEqual(json.loads(self.request('/api/log?after=0')[1]), {'entries': []})
        self.assertEqual(self.request('/api/setup', b'PK', {'Content-Type': 'application/zip'})[0], 400)
        self.assertEqual(self.request('/api/sync', b'session=other')[0], 400)
        self.assertEqual(self.request('/api/state', b'{}', {'Origin': 'http://evil.example'})[0], 403)


if __name__ == '__main__': unittest.main()

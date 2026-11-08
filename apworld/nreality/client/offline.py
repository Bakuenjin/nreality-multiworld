"""Offline test mode: the same page and game without MultiworldGG. Standard library only.

Items are simulated with the page's test item form; unlocks and checks are kept in a JSON file.
Started by tools/offline.py.
"""
import json
import os
import threading
from pathlib import Path
from typing import Any

from .bridge import EPISODES, LEVELS, GameConnection, join_numbers, parse_checks, validate_episode


class OfflineBackend:
    mode = 'local'

    def __init__(self, path: Path, session: str, starting=(0, 10, 20)) -> None:
        self.path = Path(path)
        self.lock = threading.Lock()
        self.session = session
        # items maps a receipt ID to its episode, so sending the same test item twice unlocks it once.
        self.data = dict(session=session, starting=list(starting), items={}, checks=[])
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
            if self.data['session'] != session:
                raise ValueError('State belongs to a different session')
        self.game_connection = GameConnection()

    def unlocked(self) -> list[int]:
        return sorted(set(self.data['starting']) | set(self.data['items'].values()))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2) + '\n')
        os.replace(temp, self.path)

    def receive_test_item(self, receipt: str, episode: int) -> None:
        with self.lock:
            episode = validate_episode(episode)
            if not receipt or len(receipt) > 128:
                raise ValueError('Invalid receipt ID')
            previous = self.data['items'].get(receipt)
            if previous is not None and previous != episode:
                raise ValueError('Receipt ID already belongs to another item')
            self.data['items'][receipt] = episode
            self.save()

    def sync(self, values: dict[str, str]) -> dict[str, Any]:
        with self.lock:
            if values.get('session') != self.session:
                raise ValueError('Wrong session')
            reported = parse_checks(values)
            unlocked = self.unlocked()
            if any(not 0 <= check < EPISODES * LEVELS or check // LEVELS not in unlocked for check in reported):
                raise ValueError('Invalid or locked check')
            checks = sorted(set(self.data['checks']) | reported)
            if checks != self.data['checks']:
                self.data['checks'] = checks
                self.save()
            self.game_connection.record_sync(values)
            return dict(session=self.session, unlocked=join_numbers(unlocked), checked=join_numbers(checks),
                        episodes='')

    def log_entries(self, after: int) -> list[dict[str, Any]]:
        return []

    def command(self, text: str) -> None:
        raise ValueError('Commands need a MultiworldGG connection')

    def state(self) -> dict[str, Any]:
        with self.lock:
            return dict(mode=self.mode, session=self.session, episodes=list(range(EPISODES)),
                        unlocked=self.unlocked(), checks=self.data['checks'], items=self.data['items'],
                        goal=None, server=None, **self.game_connection.state())

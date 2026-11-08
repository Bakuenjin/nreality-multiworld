"""The MultiworldGG side of the client: server connection, checks, unlocks, goal, DeathLink and the page console."""
import asyncio
import hashlib
import math
import time
import webbrowser
from typing import Any

from CommonClient import ClientCommandProcessor, CommonContext, logger
from NetUtils import ClientStatus

from .. import data
from . import bridge
from .console import INPUT_COLOR, WebConsole
from .deathlink import OwnDeathLimiter

# A DeathLink from another world that the game has not picked up within this time is dropped,
# so it cannot kill a later run.
DEATHLINK_TIMEOUT = 5


class NRealityCommandProcessor(ClientCommandProcessor):
    ctx: "NRealityContext"

    def _cmd_game(self) -> bool:
        """Open the game page in the browser."""
        webbrowser.open(self.ctx.game_url)
        return True


class NRealityContext(CommonContext):
    game = data.GAME
    items_handling = 0b111  # own items and starting inventory arrive like remote items
    command_processor = NRealityCommandProcessor

    def __init__(self, server_address: str | None = None, password: str | None = None, port: int = 8766) -> None:
        super().__init__(server_address, password)
        self.loop = asyncio.get_running_loop()
        self.game_url = f"http://127.0.0.1:{port}"
        self.game_connection = bridge.GameConnection()
        # Identifies seed, team and slot. The game keeps unconfirmed checks per session.
        self.session: str | None = None
        self.episodes: list[int] = []
        self.goal_episodes = 0
        # Kept across connection losses so a running level can still report its completion.
        self.unlocked: set[int] = set()
        self.deathlink_received_at = 0.0
        self.own_deaths = OwnDeathLimiter()
        self.console = WebConsole(self)
        self.page_commands = self.command_processor(self)
        logger.addHandler(self.console)

    async def shutdown(self) -> None:
        logger.removeHandler(self.console)
        await super().shutdown()

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "NReality Client"
        return ui

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "Connected":
            slot_data = args["slot_data"]
            identity = f"{self.server_seed_name}|{self.team}|{self.slot}"
            session = hashlib.sha256(identity.encode()).hexdigest()[:16]
            if session != self.session:
                self.game_connection = bridge.GameConnection()
                self.unlocked = set()
            self.session = session
            self.episodes = sorted(slot_data["episodes"])
            self.goal_episodes = slot_data["goal_episodes"]
            asyncio.create_task(self.update_death_link(bool(slot_data.get("death_link"))))
            self.own_deaths.configure(slot_data)
            logger.info(f"Game page: {self.game_url}")
        if cmd in ("Connected", "ReceivedItems"):
            received = {data.EPISODE_ID_TO_NUMBER.get(item.item) for item in self.items_received}
            self.unlocked |= received & set(self.episodes)
        if cmd in ("Connected", "RoomUpdate"):
            self.check_goal()

    def on_print_json(self, args: dict[str, Any]) -> None:
        try:
            self.console.add_print_json(args)
        except Exception:  # never let the page break message handling
            logger.exception("Could not show a message in the web console")
        super().on_print_json(args)

    def on_deathlink(self, data: dict[str, Any]) -> None:
        super().on_deathlink(data)
        self.deathlink_received_at = time.time()

    def send_own_deaths(self, deaths: int, cause: str, scope: str) -> None:
        now = time.time()
        left = self.own_deaths.cooldown_left(now)
        if left > 0:
            logger.info(f"DeathLink on cooldown ({math.ceil(left)} s left)")
            return
        if not self.own_deaths.count(deaths, scope):
            where = " in this level" if self.own_deaths.per_level else ""
            logger.info(f"DeathLink: {self.own_deaths.counted}/{self.own_deaths.amnesty} deaths{where}")
            return
        self.own_deaths.mark_sent(now)
        asyncio.create_task(self.send_death(f"{self.player_names.get(self.slot, self.auth)} was killed by {cause}."))

    def finished_locations(self) -> set[int]:
        """Confirmed by the server or sent and not confirmed yet."""
        return self.checked_locations | self.locations_checked

    def completed_episodes(self) -> list[int]:
        finished = self.finished_locations()
        return [ep for ep in self.episodes
                if all(data.level_location_id(ep, level) in finished for level in range(data.LEVELS_PER_EPISODE))]

    def check_goal(self) -> None:
        if self.finished_game or not self.goal_episodes or len(self.completed_episodes()) < self.goal_episodes:
            return
        # If offline, CommonClient sends the goal again after the next Connected.
        self.finished_game = True
        logger.info("Goal reached!")
        asyncio.create_task(self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]))

    # The page and the game are served from the HTTP thread; MultiworldBackend runs these on the event loop.

    def handle_game_sync(self, values: dict[str, str]) -> dict[str, Any]:
        """Takes the game's checks and deaths and answers with unlocks, confirmed checks and pending events."""
        if not self.session or values.get("session") != self.session:
            raise ValueError("Wrong session")
        accepted, dropped = set(), set()
        for check in bridge.parse_checks(values):
            episode = check // data.LEVELS_PER_EPISODE
            if not 0 <= check < data.EPISODES * data.LEVELS_PER_EPISODE or episode not in self.episodes:
                dropped.add(check)  # not part of this seed; let the game forget it
            elif episode in self.unlocked:
                accepted.add(data.check_to_location_id(check))
            # else: unlock not known yet (items still arriving); stays pending in the game
        new = accepted - self.locations_checked
        if new:
            self.locations_checked |= new
            logger.info("Completed " + ", ".join(self.location_names.lookup_in_game(loc) for loc in sorted(new)))
            asyncio.create_task(self.check_locations(new))
            self.check_goal()
        self.game_connection.record_sync(values)
        deaths = max(0, int(values.get("deaths") or 0))
        if deaths and "DeathLink" in self.tags:
            self.send_own_deaths(deaths, (values.get("cause") or "something")[:100],
                                 (values.get("deathScope") or "")[:100])
        kill = time.time() - self.deathlink_received_at < DEATHLINK_TIMEOUT
        self.deathlink_received_at = 0.0
        confirmed = {data.location_id_to_check(loc) for loc in self.checked_locations}
        # The game adds the time of each Bonus Gold once and remembers how many it has used.
        bonus_gold = sum(item.item == data.FILLER_ITEM_ID for item in self.items_received)
        return dict(session=self.session, unlocked=bridge.join_numbers(self.unlocked),
                    checked=bridge.join_numbers(confirmed | dropped), episodes=bridge.join_numbers(self.episodes),
                    deathsAck=deaths, kill=int(kill), bonusGold=bonus_gold)

    def handle_page_input(self, text: str) -> None:
        """The page's input line: answers a pending prompt, runs /commands, sends chat and !commands."""
        text = text.strip()
        if not text or len(text) > 1000:
            raise ValueError("Invalid input")
        if self.input_requests > 0:  # e.g. slot name or password prompt; not echoed
            self.input_requests -= 1
            self.input_queue.put_nowait(text)
            return
        if text.startswith(("/", "!")):
            self.console.add_text(text, "input", INPUT_COLOR)
        if not text.startswith("/") and not (self.server and self.server.socket and not self.server.socket.closed):
            self.console.add_text("Not connected to a server. Use /connect <address>.", "error")
            return
        self.page_commands(text)

    def page_state(self) -> dict[str, Any]:
        goal = None
        if self.session:
            goal = dict(required=self.goal_episodes, completed=len(self.completed_episodes()),
                        done=self.finished_game)
        return dict(mode="multiworld", session=self.session, episodes=self.episodes,
                    unlocked=sorted(self.unlocked), items=None, goal=goal,
                    checks=sorted(data.location_id_to_check(loc) for loc in self.finished_locations()),
                    server=dict(connected=self.slot is not None, address=self.server_address,
                                slot=self.auth),
                    inputRequested=self.input_requests > 0, logId=self.console.last_id,
                    **self.game_connection.state())


class MultiworldBackend:
    """bridge.Backend for a MultiworldGG connection: runs every request on the client's event loop."""
    mode = "multiworld"

    def __init__(self, ctx: NRealityContext) -> None:
        self.ctx = ctx

    def _on_event_loop(self, function, *args):
        async def run():
            return function(*args)
        return asyncio.run_coroutine_threadsafe(run(), self.ctx.loop).result(5)

    def state(self) -> dict[str, Any]:
        return self._on_event_loop(self.ctx.page_state)

    def sync(self, values: dict[str, str]) -> dict[str, Any]:
        return self._on_event_loop(self.ctx.handle_game_sync, values)

    def log_entries(self, after: int) -> list[dict[str, Any]]:
        return self._on_event_loop(self.ctx.console.entries_after, after)

    def command(self, text: str) -> None:
        self._on_event_loop(self.ctx.handle_page_input, text)

    def receive_test_item(self, receipt: str, episode: int) -> None:
        raise ValueError("Items come from the MultiworldGG server")

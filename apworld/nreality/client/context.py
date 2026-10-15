import asyncio
import hashlib
import time
import webbrowser
from typing import Any

from CommonClient import ClientCommandProcessor, CommonContext, logger
from NetUtils import ClientStatus

from .. import data
from . import bridge
from .console import INPUT_COLOR, WebConsole


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
        self.link = bridge.GameLink()
        # Identifies seed, team and slot. The SWF keeps unconfirmed checks per session.
        self.session: str | None = None
        self.episodes: list[int] = []
        self.goal_episodes = 0
        # Kept across connection losses so a running level can still report its completion.
        self.unlocked: set[int] = set()
        self.kill_requested = 0.0  # time of the last DeathLink from another world
        self.console = WebConsole(self)
        self.web_commands = self.command_processor(self)
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
            identity = f"{self.server_seed_name}|{self.team}|{self.slot}"
            session = hashlib.sha256(identity.encode()).hexdigest()[:16]
            if session != self.session:
                self.link = bridge.GameLink()
                self.unlocked = set()
            self.session = session
            self.episodes = sorted(args["slot_data"]["episodes"])
            self.goal_episodes = args["slot_data"]["goal_episodes"]
            asyncio.create_task(self.update_death_link(bool(args["slot_data"].get("death_link"))))
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
        self.kill_requested = time.time()

    def done_locations(self) -> set[int]:
        return self.checked_locations | self.locations_checked

    def completed_episodes(self) -> list[int]:
        done = self.done_locations()
        return [ep for ep in self.episodes
                if all(data.level_location_id(ep, level) in done for level in range(data.LEVELS_PER_EPISODE))]

    def check_goal(self) -> None:
        if self.finished_game or not self.goal_episodes or len(self.completed_episodes()) < self.goal_episodes:
            return
        # If offline, CommonClient sends the goal again after the next Connected.
        self.finished_game = True
        logger.info("Goal reached!")
        asyncio.create_task(self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]))

    # The following run on the event loop; MultiworldBackend calls them from the HTTP thread.
    def sync_game(self, values: dict[str, str]) -> dict[str, Any]:
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
        fresh = accepted - self.locations_checked
        if fresh:
            self.locations_checked |= fresh
            logger.info("Completed " + ", ".join(self.location_names.lookup_in_game(loc) for loc in sorted(fresh)))
            asyncio.create_task(self.check_locations(fresh))
            self.check_goal()
        self.link.seen(values)
        deaths = max(0, int(values.get("deaths") or 0))
        if deaths and "DeathLink" in self.tags:  # several deaths within one second count once
            cause = values.get("cause") or "something"
            asyncio.create_task(self.send_death(f"{self.player_names.get(self.slot, self.auth)} was killed by {cause}."))
        # Deaths from other worlds older than a few seconds are dropped instead of hitting a later run.
        kill = time.time() - self.kill_requested < 5
        self.kill_requested = 0.0
        confirmed = {data.location_id_to_check(loc) for loc in self.checked_locations}
        return dict(session=self.session, unlocked=bridge.join(self.unlocked),
                    checked=bridge.join(confirmed | dropped), episodes=bridge.join(self.episodes),
                    deathsAck=deaths, kill=int(kill))

    def web_command(self, text: str) -> None:
        """Input line of the page: answers a pending prompt, runs /commands, sends chat and !commands."""
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
        self.web_commands(text)

    def game_snapshot(self) -> dict[str, Any]:
        goal = None
        if self.session:
            goal = dict(required=self.goal_episodes, completed=len(self.completed_episodes()),
                        done=self.finished_game)
        return dict(mode="multiworld", session=self.session, episodes=self.episodes,
                    unlocked=sorted(self.unlocked), items=None, goal=goal,
                    checks=sorted(data.location_id_to_check(loc) for loc in self.done_locations()),
                    server=dict(connected=self.slot is not None, address=self.server_address,
                                slot=self.auth),
                    inputRequested=self.input_requests > 0, logId=self.console.last_id,
                    **self.link.snapshot())


class MultiworldBackend:
    """Bridge backend that hands every request to the client's event loop."""
    mode = "multiworld"

    def __init__(self, ctx: NRealityContext) -> None:
        self.ctx = ctx

    def _call(self, function, *args):
        async def run():
            return function(*args)
        return asyncio.run_coroutine_threadsafe(run(), self.ctx.loop).result(5)

    def snapshot(self) -> dict[str, Any]:
        return self._call(self.ctx.game_snapshot)

    def sync(self, values: dict[str, str]) -> dict[str, Any]:
        return self._call(self.ctx.sync_game, values)

    def log(self, after: int) -> list[dict[str, Any]]:
        return self._call(self.ctx.console.since, after)

    def command(self, text: str) -> None:
        self._call(self.ctx.web_command, text)

    def receive(self, receipt, episode) -> None:
        raise ValueError("Items come from the MultiworldGG server")

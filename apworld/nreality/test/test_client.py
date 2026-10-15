import asyncio
import time
import unittest
from unittest import mock

import test  # noqa: F401  # disables host.yaml autosave during tests
from CommonClient import logger
from NetUtils import NetworkItem, NetworkSlot, SlotType

from .. import data
from ..client.context import MultiworldBackend, NRealityContext


class ClientTestBase(unittest.IsolatedAsyncioTestCase):
    death_link = False

    async def asyncSetUp(self) -> None:
        self.ctx = NRealityContext()
        self.connect(slot=1)
        self.receive(199)

    async def asyncTearDown(self) -> None:
        self.ctx.keep_alive_task.cancel()
        logger.removeHandler(self.ctx.console)

    def connect(self, slot: int) -> None:
        ctx = self.ctx
        ctx.server_seed_name, ctx.team, ctx.slot = "seed", 0, slot
        ctx.slot_info = {0: NetworkSlot("Archipelago", "Archipelago", SlotType.player),
                         **{player: NetworkSlot(f"P{player}", data.GAME, SlotType.player) for player in (1, 2, 3)}}
        ctx.missing_locations = {data.level_location_id(ep, level) for ep in (198, 199) for level in range(5)}
        ctx.on_package("Connected", {"slot_data": {"episodes": [198, 199], "goal_episodes": 1,
                                                   "death_link": self.death_link}})

    def receive(self, episode: int) -> None:
        self.ctx.items_received.append(NetworkItem(data.episode_item_id(episode), -2, 0, 0))
        self.ctx.on_package("ReceivedItems", {})

    def sync(self, checks: str) -> dict:
        return self.ctx.sync_game({"session": self.ctx.session, "checks": checks})


class TestClientSync(ClientTestBase):
    async def test_wrong_session_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.ctx.sync_game({"session": "other", "checks": "995"})

    async def test_acknowledged_only_after_server_confirmation(self) -> None:
        self.assertEqual(self.sync("995")["checked"], "")
        location = data.level_location_id(199, 0)
        self.assertIn(location, self.ctx.locations_checked)
        self.ctx.checked_locations.add(location)
        self.assertEqual(self.sync("995")["checked"], "995")

    async def test_locked_episode_stays_pending_and_foreign_episode_is_dropped(self) -> None:
        result = self.sync("990,5")
        self.assertEqual(result["checked"], "5")  # episode 1 is not part of this seed
        self.assertNotIn(data.level_location_id(198, 0), self.ctx.locations_checked)
        self.receive(198)
        self.sync("990")
        self.assertIn(data.level_location_id(198, 0), self.ctx.locations_checked)

    async def test_unlocks_survive_connection_loss_but_not_slot_change(self) -> None:
        self.ctx.reset_server_state()
        self.assertEqual(self.sync("996")["unlocked"], "199")
        self.connect(slot=2)
        self.assertEqual(self.ctx.unlocked, set())

    async def test_goal_after_full_episode(self) -> None:
        self.sync("995,996,997,998")
        self.assertFalse(self.ctx.finished_game)
        self.sync("999")
        self.assertTrue(self.ctx.finished_game)
        self.assertEqual(self.ctx.game_snapshot()["goal"], {"required": 1, "completed": 1, "done": True})

    async def test_backend_runs_on_event_loop_from_http_thread(self) -> None:
        backend = MultiworldBackend(self.ctx)
        result = await asyncio.to_thread(backend.sync, {"session": self.ctx.session, "checks": "995"})
        self.assertEqual(result["episodes"], "198,199")
        self.assertIn(data.level_location_id(199, 0), self.ctx.locations_checked)
        self.assertTrue((await asyncio.to_thread(backend.snapshot))["connected"])
        with self.assertRaises(ValueError):
            await asyncio.to_thread(backend.receive, "x", 198)


class TestWebConsole(ClientTestBase):
    def test_print_json_becomes_coloured_segments(self) -> None:
        self.ctx.player_names = {0: "Archipelago", 1: "Ninja", 2: "Friend"}
        self.ctx.on_print_json({"type": "ItemSend", "receiving": 1,
                                "item": NetworkItem(data.episode_item_id(198), data.level_location_id(199, 3), 2, 1),
                                "data": [{"type": "player_id", "text": "2"}, {"text": " sent "},
                                         {"type": "item_id", "text": str(data.episode_item_id(198)),
                                          "player": 1, "flags": 1}]})
        entry = self.ctx.console.since(0)[-1]
        self.assertTrue(entry["relevant"])
        self.assertEqual([part["text"] for part in entry["parts"]], ["Friend", " sent ", "Episode 198"])
        self.assertEqual(entry["parts"][2]["color"], "#FFC500")  # progression colour of the text client

    def test_foreign_item_finds_are_marked(self) -> None:
        self.ctx.player_names = {0: "Archipelago", 1: "Ninja", 2: "A", 3: "B"}
        self.ctx.on_print_json({"type": "ItemSend", "receiving": 3, "item": NetworkItem(1, 1, 2, 0),
                                "data": [{"text": "A found something for B"}]})
        self.assertFalse(self.ctx.console.since(0)[-1]["relevant"])

    def test_client_log_lines_and_commands(self) -> None:
        start = self.ctx.console.last_id
        self.ctx.web_command("/received")
        texts = [part["text"] for entry in self.ctx.console.since(start) for part in entry["parts"]]
        self.assertEqual(texts[0], "/received")  # echoed input
        self.assertTrue(any("Episode 199" in text for text in texts[1:]))  # command output via the logger

    def test_chat_needs_connection_and_prompts_take_the_input(self) -> None:
        self.ctx.web_command("hello")
        self.assertEqual(self.ctx.console.since(0)[-1]["kind"], "error")
        self.ctx.input_requests = 1
        self.ctx.web_command("Ninja")
        self.assertEqual(self.ctx.input_queue.get_nowait(), "Ninja")
        self.assertFalse(self.ctx.game_snapshot()["inputRequested"])
        with self.assertRaises(ValueError):
            self.ctx.web_command("   ")


class TestDeathLink(ClientTestBase):
    death_link = True

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await asyncio.sleep(0.05)  # update_death_link from the Connected handler
        self.assertIn("DeathLink", self.ctx.tags)
        self.ctx.player_names[1] = "Ninja"
        self.ctx.send_death = mock.AsyncMock()

    async def test_deaths_are_sent_once_and_acknowledged(self) -> None:
        result = self.ctx.sync_game({"session": self.ctx.session, "deaths": "2", "cause": "a zap drone"})
        await asyncio.sleep(0.05)
        self.assertEqual(result["deathsAck"], 2)
        self.ctx.send_death.assert_awaited_once_with("Ninja was killed by a zap drone.")
        self.assertEqual(self.sync("")["deathsAck"], 0)
        self.ctx.send_death.assert_awaited_once()

    async def test_no_death_link_without_the_option(self) -> None:
        self.ctx.tags.discard("DeathLink")
        result = self.ctx.sync_game({"session": self.ctx.session, "deaths": "1", "cause": "fall damage"})
        await asyncio.sleep(0.05)
        self.assertEqual(result["deathsAck"], 1)  # acknowledged so the game forgets it
        self.ctx.send_death.assert_not_awaited()

    async def test_received_death_reaches_the_game_once_and_only_while_fresh(self) -> None:
        self.ctx.on_deathlink({"time": time.time(), "source": "Friend", "cause": "Friend fell."})
        self.assertEqual(self.sync("")["kill"], 1)
        self.assertEqual(self.sync("")["kill"], 0)
        self.ctx.on_deathlink({"time": time.time(), "source": "Friend"})
        self.ctx.kill_requested -= 10
        self.assertEqual(self.sync("")["kill"], 0)

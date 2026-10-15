import unittest

from test.bases import WorldTestBase
from test.general import gen_steps, setup_multiworld
from worlds.AutoWorld import call_all

from .. import data
from ..world import NRealityWorld


class NRealityTestBase(WorldTestBase):
    game = data.GAME
    world: NRealityWorld


class TestDefaults(NRealityTestBase):
    def test_episode_selection(self) -> None:
        self.assertEqual(len(self.world.episodes), 20)
        self.assertTrue(all(ep % 10 <= 4 for ep in self.world.episodes))
        self.assertEqual(len(self.world.starting), 3)
        self.assertEqual(self.world.goal_episodes, 10)
        locations = [loc for loc in self.multiworld.get_locations(self.player) if loc.address is not None]
        self.assertEqual(len(locations), 100)

    def test_item_pool_matches_locations(self) -> None:
        pool = [item for item in self.multiworld.itempool if item.player == self.player]
        episodes = [item for item in pool if item.name != data.FILLER_ITEM]
        self.assertEqual(len(pool), 100)
        self.assertEqual(len(episodes), 17)  # three episodes are precollected
        starting = {data.episode_item_name(ep) for ep in self.world.starting}
        self.assertFalse(starting & {item.name for item in episodes})

    def test_episode_item_unlocks_its_levels(self) -> None:
        for ep in self.world.starting:
            self.assertTrue(self.can_reach_location(data.level_location_name(ep, 4)))
        locked = next(ep for ep in self.world.episodes if ep not in self.world.starting)
        location = data.level_location_name(locked, 0)
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name(data.episode_item_name(locked))
        self.assertTrue(self.can_reach_location(location))

    def test_goal_needs_enough_episodes(self) -> None:
        missing = [data.episode_item_name(ep) for ep in self.world.episodes if ep not in self.world.starting]
        self.collect_by_name(missing[:self.world.goal_episodes - len(self.world.starting) - 1])
        self.assertBeatable(False)
        self.collect_by_name(missing[self.world.goal_episodes - len(self.world.starting) - 1])
        self.assertBeatable(True)


class TestStartInventoryForcesEpisode(unittest.TestCase):
    options = {"episode_columns": ["00-09"], "episode_count": 3, "starting_episodes": 1,
               "start_inventory": {"Episode 199": 1}}

    def test_forced_episode(self) -> None:
        # WorldTestBase skips start_inventory; mirror Main.py, which precollects it after generate_early.
        multiworld = setup_multiworld(NRealityWorld, ("generate_early",), options=self.options)
        multiworld.push_precollected(multiworld.create_item("Episode 199", 1))
        for step in gen_steps[1:]:
            call_all(multiworld, step)
        world = multiworld.worlds[1]
        self.assertIn(199, world.episodes)
        self.assertEqual(len(world.episodes), 3)
        self.assertEqual(world.starting, [])
        pool = {item.name for item in multiworld.itempool}
        self.assertNotIn("Episode 199", pool)
        self.assertTrue(multiworld.get_location("Level 199-4", 1).can_reach(multiworld.state))


class TestFiltersLimitCount(NRealityTestBase):
    options = {"episode_columns": ["00-09"], "max_episode_row": 1, "episode_count": 50, "goal_percentage": 100}

    def test_filtered_pool(self) -> None:
        self.assertEqual(self.world.episodes, [0, 1])
        self.assertEqual(sorted(self.world.starting), [0, 1])
        self.assertEqual(self.world.goal_episodes, 2)
        self.assertEqual(self.world.fill_slot_data()["episodes"], [0, 1])

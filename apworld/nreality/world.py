import math
from collections.abc import Mapping
from typing import Any

from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from Options import OptionError
from rule_builder.rules import Has, HasFromList
from worlds.AutoWorld import WebWorld, World

from . import data
from .options import NRealityOptions, option_groups


class NRealityItem(Item):
    game = data.GAME


class NRealityLocation(Location):
    game = data.GAME


class NRealityWebWorld(WebWorld):
    game = data.GAME
    theme = "stone"
    game_info_languages = ["en", "de"]
    tutorials = [
        Tutorial("Multiworld Setup Guide", "A guide to setting up NReality for MultiworldGG.",
                 "English", "setup_en.md", "setup/en", ["NReality Multiworld"]),
        Tutorial("Multiworld Setup Guide", "A guide to setting up NReality for MultiworldGG.",
                 "German", "setup_de.md", "setup/de", ["NReality Multiworld"]),
    ]
    option_groups = option_groups


class NRealityWorld(World):
    """
    N is a physics platformer about a ninja who jumps, wall-jumps and dodges drones to reach the exit.
    Every episode item unlocks five levels; finishing a level for the first time is a check.
    """

    game = data.GAME
    web = NRealityWebWorld()
    options_dataclass = NRealityOptions
    options: NRealityOptions

    item_name_to_id = data.ITEM_NAME_TO_ID
    location_name_to_id = data.LOCATION_NAME_TO_ID
    item_name_groups = {
        "Episodes": {data.episode_item_name(ep) for ep in range(data.EPISODES)},
        **{f"Column {name}": {data.episode_item_name(column * 10 + row) for row in range(10)}
           for column, name in enumerate(data.COLUMN_NAMES)},
    }
    location_name_groups = {
        data.episode_item_name(ep): {data.level_location_name(ep, level)
                                     for level in range(data.LEVELS_PER_EPISODE)}
        for ep in range(data.EPISODES)
    }

    episodes: list[int]
    starting: list[int]
    goal_episodes: int

    def generate_early(self) -> None:
        columns = self.options.episode_columns.value
        eligible = [ep for ep in range(data.EPISODES)
                    if data.column_name(ep // 10) in columns and ep % 10 <= self.options.max_episode_row.value]
        # Episodes the player starts with via start_inventory always belong to the seed.
        start_names = set(self.options.start_inventory.value)
        forced = [ep for ep in range(data.EPISODES) if data.episode_item_name(ep) in start_names]
        eligible = [ep for ep in eligible if ep not in forced]
        if not eligible and not forced:
            raise OptionError(f"{self.player_name}: no NReality episode matches the column and row filters")
        count = max(len(forced), min(self.options.episode_count.value, len(forced) + len(eligible)))
        self.episodes = sorted(forced + self.random.sample(eligible, count - len(forced)))
        # Prefer the easiest rows for the starting episodes, randomly within a row.
        order = [ep for ep in self.episodes if ep not in forced]
        self.random.shuffle(order)
        order.sort(key=lambda ep: ep % 10)
        self.starting = order[:max(0, self.options.starting_episodes.value - len(forced))]
        self.goal_episodes = max(1, math.ceil(len(self.episodes) * self.options.goal_percentage.value / 100))

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        for ep in self.episodes:
            name = data.episode_item_name(ep)
            region = Region(name, self.player, self.multiworld)
            region.add_locations({data.level_location_name(ep, level): data.level_location_id(ep, level)
                                  for level in range(data.LEVELS_PER_EPISODE)}, NRealityLocation)
            self.multiworld.regions.append(region)
            menu.connect(region, f"Play {name}", Has(name))
        menu.add_event("Goal", data.GOAL_EVENT,
                       HasFromList(*map(data.episode_item_name, self.episodes), count=self.goal_episodes),
                       location_type=NRealityLocation, item_type=NRealityItem)

    def create_item(self, name: str) -> NRealityItem:
        classification = ItemClassification.filler if name == data.FILLER_ITEM else ItemClassification.progression
        return NRealityItem(name, classification, self.item_name_to_id[name], self.player)

    def create_items(self) -> None:
        precollected = {item.name for item in self.multiworld.precollected_items[self.player]}
        for ep in self.starting:
            self.push_precollected(self.create_item(data.episode_item_name(ep)))
        pool = [self.create_item(data.episode_item_name(ep)) for ep in self.episodes
                if ep not in self.starting and data.episode_item_name(ep) not in precollected]
        missing = len(self.multiworld.get_unfilled_locations(self.player)) - len(pool)
        pool += [self.create_filler() for _ in range(missing)]
        self.multiworld.itempool += pool

    def get_filler_item_name(self) -> str:
        return data.FILLER_ITEM

    def set_rules(self) -> None:
        self.set_completion_rule(Has(data.GOAL_EVENT))

    def fill_slot_data(self) -> Mapping[str, Any]:
        return dict(episodes=self.episodes, goal_episodes=self.goal_episodes,
                    death_link=bool(self.options.death_link),
                    world_version=self.world_version.as_simple_string())

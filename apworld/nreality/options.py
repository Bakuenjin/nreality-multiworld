from dataclasses import dataclass

from Options import DeathLink, OptionGroup, OptionSet, PerGameCommonOptions, Range

from .data import COLUMN_NAMES


class EpisodeColumns(OptionSet):
    """
    Episode columns that may appear in the seed. A column holds ten consecutive episodes.
    00-09 to 90-99 are the original N v1.4 episodes, 100-109 to 190-199 the NReality columns.
    """

    display_name = "Episode Columns"
    valid_keys = COLUMN_NAMES
    default = frozenset(COLUMN_NAMES)


class MaxEpisodeRow(Range):
    """
    Difficulty filter: only episodes whose last digit is at most this value are used.
    Within a column, episodes get harder from x0 to x9. 9 allows every episode.
    """

    display_name = "Max Episode Row"
    range_start = 0
    range_end = 9
    default = 4


class EpisodeCount(Range):
    """
    Number of episodes in the seed. Every episode adds five levels, each one a check.
    Limited by the episodes left after the column and row filters.
    """

    display_name = "Episode Count"
    range_start = 1
    range_end = 200
    default = 20


class StartingEpisodes(Range):
    """
    Number of episodes unlocked from the start. The easiest episodes of the seed are preferred.
    """

    display_name = "Starting Episodes"
    range_start = 1
    range_end = 10
    default = 3


class GoalPercentage(Range):
    """
    Percentage of the seed's episodes that must be fully completed (all five levels) to win.
    """

    display_name = "Goal Percentage"
    range_start = 1
    range_end = 100
    default = 50


@dataclass
class NRealityOptions(PerGameCommonOptions):
    episode_columns: EpisodeColumns
    max_episode_row: MaxEpisodeRow
    episode_count: EpisodeCount
    starting_episodes: StartingEpisodes
    goal_percentage: GoalPercentage
    death_link: DeathLink


option_groups = [
    OptionGroup("Episodes", [EpisodeColumns, MaxEpisodeRow, EpisodeCount, StartingEpisodes]),
    OptionGroup("Goal", [GoalPercentage]),
    OptionGroup("Multiplayer", [DeathLink]),
]

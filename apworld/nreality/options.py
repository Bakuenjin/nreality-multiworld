from dataclasses import dataclass

from Options import Choice, DeathLink, OptionGroup, OptionSet, PerGameCommonOptions, Range

from .data import COLUMN_NAMES


class BoardOrder(frozenset):
    # YAML templates list a default set in iteration order; keep the columns in board order.
    def __iter__(self):
        return (name for name in COLUMN_NAMES if name in self)


class EpisodeColumns(OptionSet):
    """
    Episode columns that may appear in the seed. A column holds ten consecutive episodes.
    00-09 to 90-99 are the original N v1.4 episodes, 100-109 to 190-199 the NReality columns.
    """

    display_name = "Episode Columns"
    valid_keys = COLUMN_NAMES
    default = BoardOrder(COLUMN_NAMES)


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


class DeathLinkAmnesty(Range):
    """
    Only every Nth death of yours is sent as a DeathLink. 1 sends every death.
    DeathLinks from other players always kill your ninja.
    """

    display_name = "Death Link Amnesty"
    range_start = 1
    range_end = 20
    default = 1


class DeathLinkAmnestyScope(Choice):
    """
    Where the Death Link Amnesty count is kept.
    Across Levels: your deaths add up wherever they happen until one is sent.
    Per Level: every level starts with the full amnesty. The count starts over when you finish a level
    or die in a different one.
    """

    display_name = "Death Link Amnesty Scope"
    option_across_levels = 0
    option_per_level = 1
    default = 0


class DeathLinkCooldown(Range):
    """
    Seconds after sending a DeathLink in which your deaths are neither sent nor counted. 0 turns it off.
    DeathLinks from other players always kill your ninja.
    """

    display_name = "Death Link Cooldown"
    range_start = 0
    range_end = 600
    default = 120


@dataclass
class NRealityOptions(PerGameCommonOptions):
    episode_columns: EpisodeColumns
    max_episode_row: MaxEpisodeRow
    episode_count: EpisodeCount
    starting_episodes: StartingEpisodes
    goal_percentage: GoalPercentage
    death_link: DeathLink
    death_link_amnesty: DeathLinkAmnesty
    death_link_amnesty_scope: DeathLinkAmnestyScope
    death_link_cooldown: DeathLinkCooldown


option_groups = [
    OptionGroup("Episodes", [EpisodeColumns, MaxEpisodeRow, EpisodeCount, StartingEpisodes]),
    OptionGroup("Goal", [GoalPercentage]),
    OptionGroup("Multiplayer", [DeathLink, DeathLinkAmnesty, DeathLinkAmnestyScope, DeathLinkCooldown]),
]

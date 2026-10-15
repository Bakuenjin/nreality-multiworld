"""Static episode data shared by world and client. No game content, only numbering."""
GAME = "NReality"

EPISODES = 200
LEVELS_PER_EPISODE = 5
# Episodes 0-99 are the original N v1.4 grid, 100-199 the ten NReality columns.
# A column holds ten consecutive episodes; the last digit is the row (x0 easiest).
COLUMNS = EPISODES // 10
BASE_EPISODES = 100

FILLER_ITEM = "Bonus Gold"
FILLER_ITEM_ID = 1000
GOAL_EVENT = "Victory"


def column_name(column: int) -> str:
    return f"{column * 10:02d}-{column * 10 + 9:02d}"


COLUMN_NAMES = [column_name(column) for column in range(COLUMNS)]


def episode_item_name(episode: int) -> str:
    return f"Episode {episode:02d}"


def episode_item_id(episode: int) -> int:
    return 1 + episode


def level_location_name(episode: int, level: int) -> str:
    return f"Level {episode:02d}-{level}"


def check_index(episode: int, level: int) -> int:
    """Index used by the game mod: episode * 5 + level (0..999)."""
    return episode * LEVELS_PER_EPISODE + level


def level_location_id(episode: int, level: int) -> int:
    return 1 + check_index(episode, level)


def location_id_to_check(location_id: int) -> int:
    return location_id - 1


def check_to_location_id(check: int) -> int:
    return check + 1


ITEM_NAME_TO_ID = {episode_item_name(ep): episode_item_id(ep) for ep in range(EPISODES)}
ITEM_NAME_TO_ID[FILLER_ITEM] = FILLER_ITEM_ID
EPISODE_ID_TO_NUMBER = {episode_item_id(ep): ep for ep in range(EPISODES)}

LOCATION_NAME_TO_ID = {
    level_location_name(ep, level): level_location_id(ep, level)
    for ep in range(EPISODES) for level in range(LEVELS_PER_EPISODE)
}

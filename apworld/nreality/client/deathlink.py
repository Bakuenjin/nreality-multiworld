"""Which of the player's own deaths become DeathLinks. DeathLinks from other players are never limited."""
from dataclasses import dataclass
from typing import Any


@dataclass
class OwnDeathLimiter:
    amnesty: int = 1          # only every Nth death is sent
    per_level: bool = False   # the count starts over in a new scope (see count)
    cooldown: float = 0.0     # seconds after a sent DeathLink in which deaths are neither sent nor counted
    counted: int = 0
    scope: str = ""
    last_sent: float = 0.0

    def configure(self, slot_data: dict[str, Any]) -> None:
        # Seeds generated before these options existed send every death.
        self.amnesty = slot_data.get("death_link_amnesty", 1)
        self.per_level = slot_data.get("death_link_amnesty_scope") == "per_level"
        self.cooldown = slot_data.get("death_link_cooldown", 0)

    def cooldown_left(self, now: float) -> float:
        return self.last_sent + self.cooldown - now

    def count(self, deaths: int, scope: str) -> bool:
        """Counts deaths and tells whether the amnesty is used up, so a DeathLink should be sent.

        The game names a death's scope as "level/stamp", where the stamp changes whenever a level is passed.
        With per-level amnesty a different scope starts the count over.
        """
        if self.per_level and scope != self.scope:
            self.counted = 0
        self.scope = scope
        self.counted += deaths
        return self.counted >= self.amnesty

    def mark_sent(self, now: float) -> None:
        self.counted = 0
        self.last_sent = now

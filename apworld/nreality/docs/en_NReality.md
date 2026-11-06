# NReality

## What does randomization do to this game?

N v1.4 and the ten NReality columns contain 200 episodes with five levels each. In the multiworld,
episodes are no longer unlocked by beating the previous one. Instead, every **Episode** item unlocks
one episode. Episodes are played like in the original: all five levels in a row with a shared time pool,
selected from the original NReality episode menu.

## What is a check?

Finishing a level for the first time in episode mode sends one check. Practise mode, demos and replays
never send checks.

## Which items are there?

- `Episode 00` to `Episode 199`: unlock the matching episode (progression).
- `Bonus Gold`: adds the time of one gold piece (2 seconds) to an episode run, once. Unlike collected gold it is
  not lost when you die: it also raises the time the level restarts with. Received outside a run, it waits for the
  next one.

## What is the goal?

Fully complete (all five levels) a configurable percentage of the episodes in your seed.

## Which options are there?

- **Episode Columns**: which columns may appear (00-99 original game, 100-199 NReality).
- **Max Episode Row**: difficulty filter by the last digit of the episode number.
- **Episode Count**: how many episodes, and thus how many checks (five each), the seed contains.
- **Starting Episodes**: how many episodes are open from the start; the easiest are preferred.
- **Goal Percentage**: share of episodes that must be fully completed.

Putting `Episode XX` into `start_inventory` always adds that episode to your seed.

## DeathLink

With the `death_link` option, dying in a level kills the other DeathLink players, and their deaths kill your ninja
while you are running through a level. Deaths by enemies, fall damage, being crushed and running out of time count.
Suicide with the kill key never sends a DeathLink. Practise mode, demos and replays are ignored.

Since dying is part of playing N, two options limit only the deaths you send:
`death_link_amnesty` sends only every Nth death, and `death_link_cooldown` (default 120 seconds) ignores your
deaths for a while after sending one. With `death_link_amnesty_scope: per_level`, every level starts with the full
amnesty: the count starts over when you finish a level or die in a different one. DeathLinks from other players
always kill your ninja.

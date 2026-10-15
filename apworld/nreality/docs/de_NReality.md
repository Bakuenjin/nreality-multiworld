# NReality

## Was verändert die Randomisierung?

N v1.4 und die zehn NReality-Spalten enthalten 200 Episoden mit je fünf Levels. In der Multiworld
werden Episoden nicht mehr durch das Abschließen der vorherigen freigeschaltet. Stattdessen schaltet
jedes **Episode**-Item genau eine Episode frei. Gespielt wird wie im Original: alle fünf Levels am Stück
mit gemeinsamem Zeitvorrat, ausgewählt im originalen NReality-Episodenmenü.

## Was ist ein Check?

Der erste Abschluss eines Levels im Episodenmodus sendet einen Check. Übungsmodus, Demos und Replays
senden keine Checks.

## Welche Items gibt es?

- `Episode 00` bis `Episode 199`: schalten die jeweilige Episode frei (Progression).
- `Bonus Gold`: Füll-Item ohne spielerische Wirkung.

## Was ist das Ziel?

Einen einstellbaren Prozentsatz der Episoden des Seeds vollständig (alle fünf Levels) abschließen.

## Welche Optionen gibt es?

- **Episode Columns**: erlaubte Spalten (00–99 Originalspiel, 100–199 NReality).
- **Max Episode Row**: Schwierigkeitsfilter über die letzte Ziffer der Episodennummer.
- **Episode Count**: Anzahl der Episoden und damit der Checks (je fünf) im Seed.
- **Starting Episodes**: anfangs offene Episoden; die leichtesten werden bevorzugt.
- **Goal Percentage**: Anteil der Episoden, die vollständig abgeschlossen werden müssen.

`Episode XX` im `start_inventory` nimmt diese Episode immer in den Seed auf.

## DeathLink

Mit der Option `death_link` tötet ein Tod im Level die anderen DeathLink-Spieler, und deren Tode töten deinen Ninja,
während du ein Level spielst. Es zählen Tode durch Gegner, Fallschaden, Zerquetschen und abgelaufene Zeit.
Selbstmord mit der Kill-Taste sendet nie einen DeathLink. Übungsmodus, Demos und Replays werden ignoriert.

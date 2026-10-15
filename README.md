# NReality Multiworld

[MultiworldGG](https://multiworld.gg) support for **N v1.4** with the NReality map packs: 200 episodes, 1,000 levels.
An episode item unlocks that episode; beating a level for the first time is a check.
DeathLink is supported (suicides don't count).

## Playing

1. Install MultiworldGG and double-click `nreality.apworld`.
2. Start **NReality Client** from the launcher.
3. On first start, select your own `NReality6g2.zip` ([n.infunity.com](https://n.infunity.com/)) on the page that opens.
4. Type `/connect <address>` in the console on the right, enter your slot name and play.

Your player YAML can be created with the **Options Creator** in the MultiworldGG launcher, or start from the
`NReality.yaml` attached to the release.

The client builds the game from the ZIP (no Java needed), downloads Ruffle once and keeps both in the MultiworldGG
user folder under `nreality/`. This project ships no game files.
See the [setup guide](apworld/nreality/docs/setup_en.md) ([Deutsch](apworld/nreality/docs/setup_de.md)).

## Layout

| Path | Contents |
| --- | --- |
| `apworld/nreality/` | MultiworldGG world: items, locations, options, goal, DeathLink |
| `apworld/nreality/client/` | Client: game bridge, web text client, patcher, game files, game page (`web/`) |
| `apworld/nreality/client/bootstrap.bin` | Compiled mod code from `mod/bootstrap.as`, the only game code that is distributed |
| `mod/bootstrap.as` | The mod: unlocks, check detection, NReality episode menu, DeathLink |
| `tools/build_mod.py` | Development build: compiles the bootstrap with JPEXS, updates `bootstrap.bin`, builds the SWF |
| `tools/bridge.py` | Offline test mode without MultiworldGG (simulated items) |
| `tests/` | Build, bridge and HTTP tests; `tests/e2e/` holds YAMLs for local test seeds |

## Development

1. Put `NReality6g2.zip` into `originals/`.
2. Extract JPEXS 26.3.0 into `.local/tools/ffdec/` and Ruffle 0.7.1 web-selfhosted into `.local/ruffle/`
   (JPEXS needs Java).
3. Run `python3 tools/build_mod.py` after every change to `mod/bootstrap.as` (`--fixture` builds the test levels).
4. `sh tools/setup_multiworldgg.sh` sets up MultiworldGG from source (pinned commit, Python 3.13, venv) under
   `.local/` and links the world into it.
5. `sh tools/mwgg.sh Launcher.py "NReality Client"` starts the client; append `-- --game-dir "$PWD/.local"` to use
   the development build instead of uploading the ZIP.
6. `sh tools/release.sh` puts the release files into `dist/`: `nreality.apworld` and the `NReality.yaml` options
   template.

To read the game's code: `python3 tools/extract.py && sh tools/decompile.sh` (output in `.local/analysis/`).

`originals/` and `.local/` (tools, MultiworldGG, game files, saves) are ignored by git.

Tools: [JPEXS](https://github.com/jindrapetrik/jpexs-decompiler/releases/tag/version26.3.0),
[Ruffle](https://github.com/ruffle-rs/ruffle/releases/tag/v0.7.1),
[MultiworldGG](https://github.com/MultiworldGG/MultiworldGG).

## Tests

```
python3 -m unittest discover -s tests -v
sh tools/mwgg.sh -m pytest worlds/nreality/test -q
```

For tests against a local server, `tests/e2e/` contains YAMLs for a seed with episode 199;
`python3 tools/build_mod.py --fixture` builds a SWF in which its levels are trivial.

## License

The code in this repository is released under the [MIT License](LICENSE). It covers this project only:
N v1.4 is by [Metanet Software](https://www.thewayoftheninja.org/), NReality and its map packs are by Unreality.
No game files are included; players use their own copy. Ruffle, which the client downloads on first start,
is licensed under MIT/Apache-2.0.

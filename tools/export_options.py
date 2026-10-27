"""Write docs/options.json for the options page. Run inside MultiworldGG: sh tools/mwgg.sh "$PWD/tools/export_options.py"

Uses the same options and groups as the player options pages on multiworld.gg.
"""
import json
import os
import sys
from inspect import cleandoc
from pathlib import Path

sys.path.insert(0, os.getcwd())  # tools/mwgg.sh runs from the MultiworldGG checkout
import Options  # noqa: E402
from worlds import AutoWorldRegister, ensure_worlds_loaded  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GAME = "NReality"


def describe(key, option):
    entry = dict(key=key, name=getattr(option, "display_name", key),
                 description=cleandoc(option.__doc__ or ""), random=bool(option.supports_weighting))
    if issubclass(option, Options.Toggle):
        entry.update(type="toggle", default=bool(option.default))
    elif issubclass(option, Options.Choice):
        entry.update(type="choice", default=option.name_lookup[option.default],
                     choices=[dict(value=name, label=option.get_option_name(value))
                              for value, name in option.name_lookup.items()])
    elif issubclass(option, Options.Range):
        entry.update(type="range", default=option.default, min=option.range_start, max=option.range_end,
                     named={name: value for name, value in getattr(option, "special_range_names", {}).items()})
    elif issubclass(option, Options.OptionSet) and option.valid_keys:
        entry.update(type="set", default=list(option.default), keys=list(option.valid_keys))
    else:
        return None  # free-form options are left to the YAML template
    return entry


def collect():
    ensure_worlds_loaded()
    world = AutoWorldRegister.world_types[GAME]
    groups = Options.get_option_groups(world, visibility_level=Options.Visibility.simple_ui)
    output = dict(game=GAME, version=world.world_version.as_simple_string(), groups=[])
    for group, options in groups.items():
        entries = [entry for key, option in options.items() if (entry := describe(key, option))]
        if entries:
            output["groups"].append(dict(name=group, options=entries))
    return output


def main():
    target = ROOT / "docs" / "options.json"
    target.write_text(json.dumps(collect(), indent=1) + "\n")
    print(target)


if __name__ == "__main__":
    main()

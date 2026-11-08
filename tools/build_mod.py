"""Development build: compile mod/bootstrap.as with JPEXS and build the SWF from the hash-pinned originals.

The compiled bootstrap tag is stored in the apworld so that players can build without Java or JPEXS.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / 'apworld/nreality/client'

# The patcher needs only the standard library; import it without the apworld package (which needs MultiworldGG).
sys.path.insert(0, str(ROOT / 'apworld' / 'nreality'))
from client import patcher  # noqa: E402


def load_originals():
    """The game files from originals/NReality6g2.zip, or else from .local/original (see tools/extract.py)."""
    archive = ROOT / 'originals/NReality6g2.zip'
    if archive.is_file():
        return patcher.read_archive(archive)
    originals = {name: (ROOT / '.local/original' / name).read_bytes() for name in patcher.ORIGINALS}
    patcher.verify(originals)
    return originals


def compile_bootstrap(originals, source, output):
    """Compiles the mod with JPEXS against the base game and returns the resulting DoAction tag."""
    output.mkdir(parents=True, exist_ok=True)
    (output / 'compiler-input.swf').write_bytes(patcher.compress_swf(patcher.base_game(originals)))
    imports = output / 'imports' / 'scripts' / 'frame_1'
    imports.mkdir(parents=True, exist_ok=True)
    (imports / 'DoAction_144.as').write_text(source)
    subprocess.run(['java', f'-Duser.home={ROOT / ".local/tools/java-home"}',
        '-jar', str(ROOT / '.local/tools/ffdec/ffdec.jar'), '-importScript',
        str(output / 'compiler-input.swf'), str(output / 'compiled.swf'),
        str(output / 'imports')], check=True)
    compiled = patcher.decompress_swf((output / 'compiled.swf').read_bytes())
    _, start, _, end = [tag for tag in patcher.iter_tags(compiled) if tag[0] == patcher.DO_ACTION][-1]
    tag = compiled[start:end]
    assert b'/api/sync' in tag, 'Bootstrap was not compiled'
    return tag


def with_test_levels(source):
    """Replaces the five levels of episode 199 with a trivial one for tests and the tests/e2e seeds.

    A flat floor with the exit to the right of the start and a mine to its left (DeathLink test).
    """
    tiles = ''.join('1' if row == 22 else '0' for col in range(31) for row in range(23))
    objects = '5^120,540!11^180,540,120,540!12^60,540'
    hook = ('MW.base.BuildGameDataWithoutTestLevels = NinjaData.prototype.BuildGameData;\n'
            'NinjaData.prototype.BuildGameData = function() {\n'
            '    MW.base.BuildGameDataWithoutTestLevels.call(this);\n'
            f'    var level = new LevelData("SMOKE TEST", "{tiles}|{objects}");\n'
            '    for (var i = 0; i < 5; i++) { this.episodeList[199].levelList[i] = level; }\n'
            '};\n')
    assert source.count('\nInitApp();') == 1, 'mod/bootstrap.as must start the game with InitApp(); once'
    return source.replace('\nInitApp();', '\n' + hook + 'InitApp();')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', action='store_true', help='Build the test levels into episode 199')
    args = parser.parse_args()
    output = ROOT / '.local/mod'
    originals = load_originals()
    source = (ROOT / 'mod/bootstrap.as').read_text()
    if args.fixture:
        source = with_test_levels(source)
    tag = compile_bootstrap(originals, source, output)
    if not args.fixture:
        (CLIENT / 'bootstrap.bin').write_bytes(tag)
        (CLIENT / 'bootstrap.json').write_text(json.dumps(dict(
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            tag_sha256=hashlib.sha256(tag).hexdigest()), indent=2) + '\n')
    result = output / ('n_multiworld_fixture.swf' if args.fixture else 'n_multiworld.swf')
    result.write_bytes(patcher.build(originals, tag))
    manifest = dict(base_sha256=patcher.ORIGINALS['n_v14.swf'],
                    output_sha256=hashlib.sha256(result.read_bytes()).hexdigest(),
                    episodes=200, levels=1000, compiler='JPEXS 26.3.0',
                    changes=['isolated SharedObject name', '10 original map-data action tags',
                             'replaced final bootstrap action only'])
    (output / ('fixture-build.json' if args.fixture else 'build.json')).write_text(json.dumps(manifest, indent=2) + '\n')
    print(result)


if __name__ == '__main__':
    main()

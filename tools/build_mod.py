"""Development build: compile mod/bootstrap.as with JPEXS and build the SWF from the hash-pinned originals.

The compiled bootstrap tag is stored in the apworld so that players can build without Java or JPEXS.
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / 'apworld/nreality/client'

_spec = importlib.util.spec_from_file_location('nreality_patcher', CLIENT / 'patcher.py')
patcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(patcher)
decode, encode, tags = patcher.decode, patcher.encode, patcher.tags


def load_originals():
    archive = ROOT / 'originals/NReality6g2.zip'
    if archive.is_file():
        return patcher.read_archive(archive)
    originals = {name: (ROOT / '.local/original' / name).read_bytes() for name in patcher.ORIGINALS}
    patcher.verify(originals)
    return originals


def compile_bootstrap(originals, source, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'compiler-input.swf').write_bytes(encode(patcher.base_game(originals)))
    imports = output / 'imports' / 'scripts' / 'frame_1'
    imports.mkdir(parents=True, exist_ok=True)
    (imports / 'DoAction_144.as').write_text(source)
    subprocess.run(['java', f'-Duser.home={ROOT / ".local/tools/java-home"}',
        '-jar', str(ROOT / '.local/tools/ffdec/ffdec.jar'), '-importScript',
        str(output / 'compiler-input.swf'), str(output / 'compiled.swf'),
        str(output / 'imports')], check=True)
    compiled = decode((output / 'compiled.swf').read_bytes())
    _, start, _, end = [tag for tag in tags(compiled) if tag[0] == patcher.DO_ACTION][-1]
    tag = compiled[start:end]
    assert b'/api/sync' in tag, 'Bootstrap was not compiled'
    return tag


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', action='store_true')
    args = parser.parse_args()
    output = ROOT / '.local/mod'
    originals = load_originals()
    source = (ROOT / 'mod/bootstrap.as').read_text()
    if args.fixture:
        tiles = ''.join('1' if row == 22 else '0' for col in range(31) for row in range(23))
        # Exit to the right of the start, a mine to the left (DeathLink test).
        fixture = 'this.episodeList[199].levelList[0] = new LevelData("SMOKE TEST", "' + tiles + '|5^120,540!11^180,540,120,540!12^60,540");'
        source = source.replace('        _root["vCol" + col].call(this);\n    }', '        _root["vCol" + col].call(this);\n    }\n    ' + fixture)
        copies = ''.join(f'\n    this.episodeList[199].levelList[{level}] = this.episodeList[199].levelList[0];' for level in range(1, 5))
        source = source.replace(fixture, fixture + copies)
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

"""Builds n_multiworld.swf from the player's own NReality 6g2 download. Standard library only.

Only our compiled bootstrap (an SWF DoAction tag) is distributed; all game data comes from the player's files.
"""
import hashlib
import struct
import zipfile
import zlib

# SHA-256 of the files used from NReality6g2.zip: the N v1.4 base game and the ten NReality map columns.
ORIGINALS = {
    'n_v14.swf': 'f0279be3426c0355a22433b532505f7ea9389e85e0739f06b3467dcfeb05a296',
    'col10.swf': '00f9b77c48c03af5df7df99801d56e8f6bbe24aca1c89fe9bd55d6db9380c7e4',
    'col11.swf': 'f6eafe27355032d56add30b9560813d896a6de31d962c60baf0ca0f5afdc8992',
    'col12.swf': '3f14fcc4bcd605b463cdacac9bec3e7d96728da8781f5f2fa61155928cb0ca5a',
    'col13.swf': '64671c38bc6fad43113597db4b2f0e088d2986d7400c17c6eae8c2d0d0f03f1f',
    'col14.swf': 'a41e64e4ec3e8a382787f54de5c7ea96168ae1b44623e0c8624a6651590970b5',
    'col15.swf': 'b3ba64938ee22f376a3f22b9af44d00bdc9606e891dfeff3c4eb1e126ef2f038',
    'col16.swf': 'bb836c24bfa2d6c4bf4d7aac3c6f1de1b6f4053b627c92e83b08ce84464188fb',
    'col17.swf': 'ca154d82412914830178d74bae1e78364d5fcb069ad39bb69e669436f17c22c4',
    'col18.swf': 'b37c2a0932dadb5a5b52f3b770475473b32c000071bc6d00332eccb2be694b38',
    'col19.swf': '25b654f3f3df7f95517bd3bc84f9fb8c555bb2474da02e0d646287d6a94dc385',
}
# Separate save data from the player's ordinary N v1.4 game (same byte length).
SAVE_NAME = (b'n_v14b_userdata', b'n_mw01_userdata')
DO_ACTION = 12


def decode(raw):
    if raw[:3] != b'CWS':
        raise ValueError('Not a compressed SWF')
    data = b'FWS' + raw[3:8] + zlib.decompress(raw[8:])
    if len(data) != struct.unpack_from('<I', data, 4)[0]:
        raise ValueError('SWF length mismatch')
    return data


def encode(data):
    return b'CWS' + data[3:4] + struct.pack('<I', len(data)) + zlib.compress(data[8:])


def tags(data):
    """Yields (code, tag start, body start, end) for every top-level tag of an uncompressed SWF."""
    pos = 8 + (5 + 4 * (data[8] >> 3) + 7) // 8 + 4
    while pos < len(data):
        start = pos
        header = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        size = header & 63
        if size == 63:
            size = struct.unpack_from('<I', data, pos)[0]
            pos += 4
        end = pos + size
        if end > len(data):
            raise ValueError('Truncated SWF tag')
        yield header >> 6, start, pos, end
        pos = end


def verify(originals):
    for name, digest in ORIGINALS.items():
        if name not in originals:
            raise ValueError(f'{name} is missing')
        if hashlib.sha256(originals[name]).hexdigest() != digest:
            raise ValueError(f'{name} is not the expected NReality 6g2 file')


def read_archive(archive):
    """Reads and verifies the needed files from NReality6g2.zip (a path or a file object)."""
    try:
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
            originals = {name: zf.read(name) for name in ORIGINALS if name in names}
    except zipfile.BadZipFile:
        raise ValueError('Not a ZIP archive') from None
    verify(originals)
    return originals


def base_game(originals):
    """The decoded base game with the separate save name; JPEXS compiles the bootstrap against this."""
    base = decode(originals['n_v14.swf'])
    if base.count(SAVE_NAME[0]) != 1:
        raise ValueError('Unexpected base game')
    return base.replace(*SAVE_NAME)


def build(originals, bootstrap_tag):
    """Copies the map columns' original DoAction tags into the base game and replaces its final bootstrap."""
    verify(originals)
    base = base_game(originals)
    actions = [tag for tag in tags(base) if tag[0] == DO_ACTION]
    if len(actions) != 144:
        raise ValueError('Unexpected base game')
    extra = b''
    for column in range(10, 20):
        col = decode(originals[f'col{column}.swf'])
        (_, start, _, end), = [tag for tag in tags(col) if tag[0] == DO_ACTION]
        extra += col[start:end]
    _, start, _, end = actions[-1]
    return encode(base[:start] + extra + bootstrap_tag + base[end:])

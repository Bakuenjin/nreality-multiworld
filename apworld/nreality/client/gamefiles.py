"""Game files in the player's folder: originals from their NReality ZIP, the built SWF and the Ruffle runtime."""
import hashlib
import io
import json
import os
import shutil
import ssl
import threading
import urllib.request
import zipfile
from pathlib import Path

from . import patcher

RUFFLE_URL = 'https://github.com/ruffle-rs/ruffle/releases/download/v0.7.1/ruffle-0.7.1-web-selfhosted.zip'
RUFFLE_SHA256 = 'ef12edbee135d581a9cd523837d746da30a07a64dbf1cf472d2e472c656f4b5e'


def bundled_bootstrap():
    # The module loader reads from a plain folder as well as from inside a zipped .apworld.
    return __loader__.get_data(os.path.join(os.path.dirname(__file__), 'bootstrap.bin'))


def download_ruffle():
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    with urllib.request.urlopen(RUFFLE_URL, timeout=60, context=context) as response:
        return response.read(64 * 1024 * 1024)


def write_atomic(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(data)
    os.replace(temp, path)


class GameFiles:
    def __init__(self, folder, bootstrap_tag, fetch_ruffle=download_ruffle):
        self.folder = Path(folder)
        self.tag = bootstrap_tag
        self.version = hashlib.sha256(bootstrap_tag).hexdigest()
        self.fetch_ruffle = fetch_ruffle
        self.swf = self.folder / 'n_multiworld.swf'
        self.ruffle = self.folder / 'ruffle'
        self.originals = self.folder / 'original'
        self.lock = threading.Lock()
        self.busy = False
        self.message = ''

    def built_version(self):
        try:
            return json.loads((self.folder / 'build.json').read_text())['bootstrap_sha256']
        except (OSError, ValueError, KeyError):
            return None

    def has_originals(self):
        return all((self.originals / name).is_file() for name in patcher.ORIGINALS)

    def ready(self):
        return (self.swf.is_file() and self.built_version() == self.version
                and (self.ruffle / 'ruffle.js').is_file())

    def state(self):
        return dict(ready=self.ready(), busy=self.busy, message=self.message)

    def install(self, archive):
        """Stores the needed files of the uploaded NReality6g2.zip and prepares the game."""
        originals = patcher.read_archive(io.BytesIO(archive))
        self.originals.mkdir(parents=True, exist_ok=True)
        for name, data in originals.items():
            write_atomic(self.originals / name, data)
        self.prepare()

    def prepare(self):
        """Rebuilds the SWF after an update of the mod and fetches Ruffle once. Safe to call repeatedly."""
        with self.lock:
            self.busy = True
            try:
                if self.has_originals() and (not self.swf.is_file() or self.built_version() != self.version):
                    self.message = 'Building the game'
                    originals = {name: (self.originals / name).read_bytes() for name in patcher.ORIGINALS}
                    write_atomic(self.swf, patcher.build(originals, self.tag))
                    write_atomic(self.folder / 'build.json', json.dumps(dict(bootstrap_sha256=self.version)).encode())
                if self.swf.is_file() and not (self.ruffle / 'ruffle.js').is_file():
                    self.message = 'Downloading Ruffle'
                    self.install_ruffle(self.fetch_ruffle())
                self.message = ''
            except Exception as error:
                self.message = str(error)
                raise
            finally:
                self.busy = False

    def install_ruffle(self, archive):
        if hashlib.sha256(archive).hexdigest() != RUFFLE_SHA256:
            raise ValueError('Ruffle download has an unexpected checksum')
        temp = self.folder / 'ruffle.tmp'
        shutil.rmtree(temp, ignore_errors=True)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            for info in zf.infolist():
                target = (temp / info.filename).resolve()
                if info.is_dir() or not target.is_relative_to(temp.resolve()):
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(info))
        if not (temp / 'ruffle.js').is_file():
            raise ValueError('Ruffle download does not contain ruffle.js')
        shutil.rmtree(self.ruffle, ignore_errors=True)
        os.replace(temp, self.ruffle)

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from ..client import gamefiles, patcher

ARCHIVE = Path(__file__).resolve().parents[3] / "originals" / "NReality6g2.zip"


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


FAKE_RUFFLE = zip_bytes({"ruffle.js": b"// ruffle", "core.wasm": b"\0", "../escape.txt": b"x"})


@unittest.skipUnless(ARCHIVE.is_file(), "needs originals/NReality6g2.zip")
class TestGameFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory())) / "nreality"
        self.enterContext(mock.patch.object(gamefiles, "RUFFLE_SHA256", hashlib.sha256(FAKE_RUFFLE).hexdigest()))
        self.downloads = 0
        self.files = gamefiles.GameFiles(self.folder, gamefiles.bundled_bootstrap(), self.fetch)

    def fetch(self) -> bytes:
        self.downloads += 1
        return FAKE_RUFFLE

    def test_setup_from_the_players_archive(self) -> None:
        self.assertFalse(self.files.state()["ready"])
        self.files.install(ARCHIVE.read_bytes())
        self.assertTrue(self.files.state()["ready"])
        expected = patcher.build(patcher.read_archive(ARCHIVE), gamefiles.bundled_bootstrap())
        self.assertEqual(self.files.swf.read_bytes(), expected)
        self.assertTrue((self.files.ruffle / "ruffle.js").is_file())
        self.assertFalse((self.folder / "escape.txt").exists())
        self.files.prepare()
        self.assertEqual(self.downloads, 1)  # Ruffle is fetched once

    def test_mod_update_rebuilds_from_stored_originals(self) -> None:
        self.files.install(ARCHIVE.read_bytes())
        (self.folder / "build.json").write_text(json.dumps({"bootstrap_sha256": "old"}))
        self.files.swf.write_bytes(b"stale")
        self.assertFalse(self.files.ready())
        self.files.prepare()
        self.assertTrue(self.files.ready())
        self.assertNotEqual(self.files.swf.read_bytes(), b"stale")

    def test_wrong_archive_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.files.install(zip_bytes({"n_v14.swf": b"not the game"}))
        with self.assertRaises(ValueError):
            self.files.install(b"no zip")
        self.assertFalse(self.files.has_originals())

    def test_ruffle_checksum_is_verified(self) -> None:
        self.files.fetch_ruffle = lambda: zip_bytes({"ruffle.js": b"tampered"})
        with self.assertRaises(ValueError):
            self.files.install(ARCHIVE.read_bytes())
        self.assertFalse(self.files.ready())
        self.assertIn("checksum", self.files.state()["message"])

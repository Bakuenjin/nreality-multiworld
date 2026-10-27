import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPORTER = ROOT / "tools" / "export_options.py"


@unittest.skipUnless(EXPORTER.is_file(), "needs the development checkout")
class TestOptionsPage(unittest.TestCase):
    def test_options_page_data_is_current(self) -> None:
        spec = importlib.util.spec_from_file_location("export_options", EXPORTER)
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        self.assertEqual(json.loads((ROOT / "docs" / "options.json").read_text()), exporter.collect(),
                         "options changed: run tools/release.sh or tools/export_options.py")

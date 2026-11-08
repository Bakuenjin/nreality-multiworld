import hashlib
import json
import unittest
from tools.build_mod import CLIENT, ROOT, load_originals, patcher


class BuildTests(unittest.TestCase):
    def test_game_bytecode_preserved_except_bootstrap_and_save_name(self):
        original = patcher.decompress_swf((ROOT / '.local/original/n_v14.swf').read_bytes())
        original = original.replace(b'n_v14b_userdata', b'n_mw01_userdata')
        result = patcher.decompress_swf((ROOT / '.local/mod/n_multiworld.swf').read_bytes())
        original_tags = [(code, original[start:end]) for code, start, _, end in patcher.iter_tags(original)]
        new_tags = [(code, result[start:end]) for code, start, _, end in patcher.iter_tags(result)]
        last = max(i for i, (code, _) in enumerate(original_tags) if code == 12)
        self.assertEqual(new_tags[:last], original_tags[:last])
        self.assertEqual(new_tags[last+11:], original_tags[last+1:])
        for col in range(10, 20):
            data = patcher.decompress_swf((ROOT / f'.local/original/col{col}.swf').read_bytes())
            action = next(data[s:e] for code, s, _, e in patcher.iter_tags(data) if code == 12)
            self.assertEqual(new_tags[last+col-10], (12, action))
        self.assertIn(b'/api/sync', new_tags[last+10][1])
        self.assertNotIn(b'SMOKE TEST', result)

    def test_bundled_bootstrap_is_current_and_builds_the_same_swf(self):
        meta = json.loads((CLIENT / 'bootstrap.json').read_text())
        source = (ROOT / 'mod/bootstrap.as').read_text()
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), meta['source_sha256'],
                         'mod/bootstrap.as changed: run tools/build_mod.py')
        tag = (CLIENT / 'bootstrap.bin').read_bytes()
        self.assertEqual(hashlib.sha256(tag).hexdigest(), meta['tag_sha256'])
        self.assertEqual(patcher.build(load_originals(), tag), (ROOT / '.local/mod/n_multiworld.swf').read_bytes())

    def test_wrong_files_are_rejected(self):
        originals = load_originals()
        originals['col10.swf'] = originals['col11.swf']
        with self.assertRaises(ValueError): patcher.build(originals, b'')


if __name__ == '__main__': unittest.main()

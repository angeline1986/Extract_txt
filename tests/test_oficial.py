import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]/'scripts/check_epub_oficial.py'
spec = importlib.util.spec_from_file_location('oficial',MODULE)
of = importlib.util.module_from_spec(spec)
spec.loader.exec_module(of)

class TestOficial(unittest.TestCase):
    def test_inject_idempotent_and_legacy_preserved(self):
        s='<!doctype html><nav class="primary-tabs" id="primaryTabs">ANTIGO</nav><section id="explorer">LEGADO</section><script>const DATA={"records":[]};</script></body>'
        once=of.inject(s,{'merges':[]})
        twice=of.inject(once,{'merges':[]})
        self.assertEqual(once,twice)
        self.assertIn('<section id="explorer">LEGADO</section>',twice)
        self.assertEqual(twice.count('<section id="oficial"'),1)
        self.assertEqual(twice.count('<button class="nav" id="nav-oficial"'),1)
    def test_reject_unknown_html(self):
        with self.assertRaises(ValueError):of.inject('<html></html>',{'merges':[]})

if __name__=='__main__':unittest.main()

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'check_epub_consolidar.py'
SPEC = importlib.util.spec_from_file_location('check_epub_consolidar', MODULE_PATH)
ce = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ce)


def record(name, title='', author='', sha='', ids=None, links=None):
    return {
        'arquivo': name,
        'titulo': title,
        'autores': [author] if author else [],
        'autor_catalogo': '',
        'sha256': sha,
        'identificadores': ids or [],
        'links': links or [],
        'erro': '',
    }


class GroupingTests(unittest.TestCase):
    def test_01_exact_sha_groups(self):
        groups = ce.grouping([record('a.epub', 'First', sha='same'), record('copy.epub', 'Other', sha='same')])
        self.assertEqual(1, len(groups))

    def test_02_seven_explicit_volumes_group(self):
        files = [record(f'WuChang Jie vol{i} - Shui Qian Cheng.epub', f'WuChang Jie vol{i}', 'Shui Qian Cheng') for i in range(1, 8)]
        groups = ce.consolidate_volumes(ce.grouping(files))
        self.assertEqual(1, len(groups))
        self.assertEqual(7, len(next(iter(groups.values()))))

    def test_03_different_titles_stay_separate(self):
        groups = ce.grouping([record('a.epub', 'WuChang Jie', 'Author A'), record('b.epub', 'Another Novel', 'Author A')])
        self.assertEqual(2, len(groups))

    def test_04_conflicting_authors_stay_separate(self):
        groups = ce.grouping([record('a.epub', 'Same Novel', 'Author A'), record('b.epub', 'Same Novel', 'Author B')])
        self.assertEqual(2, len(groups))

    def test_05_conflicting_specific_ids_stay_separate(self):
        groups = ce.grouping([
            record('a.epub', 'Same Novel', 'Author A', ids=['https://www.novelupdates.com/series/work-a/']),
            record('b.epub', 'Same Novel', 'Author A', ids=['https://www.novelupdates.com/series/work-b/']),
        ])
        self.assertEqual(2, len(groups))

    def test_06_generic_epub_metadata_is_not_identity(self):
        groups = ce.grouping([record('a.epub', 'Unknown', 'Unknown'), record('b.epub', '3902d8d9-6fdd-4235-98f0-32e1eca7edeb', 'EpubPress')])
        self.assertEqual(2, len(groups))

    def test_body_link_is_not_identity_evidence(self):
        groups = ce.grouping([
            record('a.epub', 'Novel A', 'Author', links=['https://www.novelupdates.com/series/work-a/']),
            record('b.epub', 'Novel B', 'Author', links=['https://www.novelupdates.com/series/work-a/']),
        ])
        self.assertEqual(2, len(groups))

    def test_appledouble_sidecars_are_excluded(self):
        groups = ce.grouping([record('._WuChang Jie vol1.epub', 'WuChang Jie vol1', 'Author'), record('WuChang Jie vol1.epub', 'WuChang Jie vol1', 'Author')])
        self.assertEqual(1, len(groups))
        self.assertEqual('WuChang Jie vol1.epub', next(iter(groups.values()))[0]['arquivo'])


class WorksPanelTests(unittest.TestCase):
    def test_07_known_nationality_is_hidden_value(self):
        self.assertTrue(ce.nationality_known({'pais_origem': 'CN'}))
        self.assertFalse(ce.nationality_known({'pais_origem': 'INDEFINIDO'}))

    def test_08_unknown_nationality_is_visible_value(self):
        self.assertFalse(ce.nationality_known({'pais_origem': ''}))
        self.assertFalse(ce.nationality_known({'pais_origem': 'desconhecido'}))

    def test_09_panel_searches_associated_filenames(self):
        html = ce.inject_html('<aside></aside><main></main><body></body>', {'obras': [], 'total_arquivos': 0})
        self.assertIn('...g.arquivos', html)
        self.assertIn('Ver arquivos associados', html)
        self.assertIn('cePageSize=50', html)

    def test_10_regeneration_preserves_a_single_panel(self):
        base = '<aside></aside><main></main><body></body>'
        payload = {'obras': [], 'total_arquivos': 0}
        once = ce.inject_html(base, payload)
        twice = ce.inject_html(once, payload)
        self.assertEqual(once, twice)
        self.assertEqual(1, twice.count('id="nav-works"'))
        self.assertEqual(1, twice.count('id="works"'))


if __name__ == '__main__':
    unittest.main()

import importlib.util
import json
import re
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
        self.assertIn("const detailsHeader=obrasMode?'':'<th>Detalhes</th>'", html)
        self.assertIn(".sort((a,b)=>a.titulo.localeCompare(b.titulo,'pt-BR'", html)
        self.assertIn('JSON.stringify(g.itens_serie||[])', html)
        self.assertIn('works.length', html)
        self.assertIn('works.slice(cePage*cePageSize', html)
        self.assertIn('cePageSize=50', html)

    def test_10_regeneration_preserves_a_single_panel(self):
        base = '<aside></aside><main></main><body></body>'
        payload = {'obras': [], 'total_arquivos': 0}
        once = ce.inject_html(base, payload)
        twice = ce.inject_html(once, payload)
        self.assertEqual(once, twice)
        self.assertEqual(1, twice.count('id="nav-works"'))
        self.assertEqual(1, twice.count('id="works"'))

    def test_bungo_volumes_render_as_one_row_and_keep_details(self):
        titles = [
            ('Bungo Stray Dogs, Vol. 5: Dead Apple', 'Hiro Iwahata and Ganjii', 'b5.epub'),
            ('Bungo Stray Dogs, Vol. 6: Beast', 'Kafka Asagiri and Sango Harukawa', 'b6.epub'),
            ('Bungo Stray Dogs, Vol. 7: Dazai, Chuuya, Age Fifteen', 'Kafka Asagiri and Sango Harukawa', 'b7.epub'),
            ('Bungo Stray Dogs, Vol. 8: Storm Bringer', 'Kafka Asagiri and Sango Harukawa', 'b8.epub'),
        ]
        payload = {'obras': [{'titulo': title, 'autores': [author], 'arquivos': [file],
                              'quantidade': 1, 'titulos_alternativos': []}
                             for title, author, file in titles]}
        view = ce.presentation_obras(payload)
        self.assertEqual(1, len(view['obras']))
        row = view['obras'][0]
        self.assertEqual('Bungo Stray Dogs', row['titulo'])
        self.assertEqual(4, row['quantidade'])
        self.assertEqual([title for title, _, _ in titles], [child['titulo'] for child in row['itens_serie']])
        self.assertEqual([file for _, _, file in titles], row['arquivos'])
        self.assertEqual(4, len(payload['obras']))  # persisted JSON object remains untouched
        base = '<aside></aside><main></main><body></body>'
        once = ce.inject_html(base, payload)
        twice = ce.inject_html(once, payload)
        encoded = re.search(r'const CE_DATA=(.*?);\nconst ceEsc', twice, re.S).group(1)
        rendered = json.loads(encoded)['obras']
        self.assertEqual(1, len(rendered))
        self.assertEqual(4, len(rendered[0]['itens_serie']))

    def test_wuchang_existing_seven_file_row_stays_one_line(self):
        payload = {'obras': [{'titulo': 'WuChang Jie', 'autores': ['Shui Qian Cheng'],
                              'arquivos': [f'WuChang Jie vol{i}.epub' for i in range(1, 8)],
                              'quantidade': 7,
                              'titulos_alternativos': [f'WuChang Jie vol{i}' for i in range(1, 8)]}]}
        view = ce.presentation_obras(payload)
        self.assertEqual(1, len(view['obras']))
        self.assertEqual(7, view['obras'][0]['quantidade'])
        self.assertEqual(7, len(view['obras'][0]['itens_serie']))
        self.assertEqual('Shui Qian Cheng', view['obras'][0]['itens_serie'][0]['autores'][0])

    def test_base_title_row_uses_one_explicit_alternate_volume(self):
        payload = {'obras': [
            {'titulo': 'Bungo Stray Dogs', 'titulos_alternativos': ['Bungo Stray Dogs, Vol. 2'],
             'autores': ['Kafka Asagiri'], 'arquivos': ['b2.epub'], 'quantidade': 1},
            {'titulo': 'Bungo Stray Dogs, Vol. 5: Dead Apple', 'autores': ['Hiro Iwahata'],
             'arquivos': ['b5.epub'], 'quantidade': 1},
        ]}
        view = ce.presentation_obras(payload)
        self.assertEqual(1, len(view['obras']))
        self.assertEqual(2, view['obras'][0]['quantidade'])
        self.assertEqual(['Bungo Stray Dogs, Vol. 2', 'Bungo Stray Dogs, Vol. 5: Dead Apple'],
                         [child['titulo'] for child in view['obras'][0]['itens_serie']])

    def test_different_bases_and_ambiguous_duplicate_volumes_stay_separate(self):
        payload = {'obras': [
            {'titulo': 'Bungo Stray Dogs Vol. 5: Dead Apple', 'autores': [], 'arquivos': ['5.epub'], 'quantidade': 1},
            {'titulo': 'Bungo Stray Dogs Vol. 5: Adaptation', 'autores': [], 'arquivos': ['5-alt.epub'], 'quantidade': 1},
            {'titulo': 'Another Dogs Vol. 6: Beast', 'autores': [], 'arquivos': ['6.epub'], 'quantidade': 1},
        ]}
        view = ce.presentation_obras(payload)
        self.assertEqual(3, len(view['obras']))

    def test_user_identified_daomu_biji_franchise_stays_as_distinct_details(self):
        names = [
            "The Grave Robbers’ Chronicles Restart Final Version",
            "The Grave Robbers’ Chronicles Post Restart Sequels Final Version",
            "The Grave Robbers’ Chronicles The Mystic Nine Final Version Updated",
            "The Mystic Nine",
            "The Grave Robbers’ Chronicles The Southern Archives Final Version 2",
            "The Grave Robbers' Chronicles A Thousand Faces Final Version",
            "The Grave Robbers’ Chronicles Volume New Years Specials and Extras Final Version",
            "The Grave Robbers’ Chronicles Notes in Rain Village Final Version",
            "The Grave Robbers’ Chronicles Wu Xie's Private Notes Final Version",
            'Moving Forward Through The Flowery Night The End Comes Without A Sound Final Version',
            'The Mystic Nine Extras',
        ]
        payload = {'obras': [{'titulo': name, 'autores': ['Xu Lei'], 'arquivos': [f'{i}.epub'],
                              'quantidade': 1, 'titulos_alternativos': []}
                             for i, name in enumerate(names)] + [
            {'titulo': 'The Grave Robbers’ Chronicles Final Version', 'autores': ['Xu Lei'],
             'arquivos': ['main Volume 1.epub', 'main Volume 2.epub'], 'quantidade': 2,
             'titulos_alternativos': ['The Grave Robbers’ Chronicles Volume 1 Final Version',
                                      'The Grave Robbers’ Chronicles Volume 2 Final Version']},
            {'titulo': 'Daomu Biji', 'autores': ['Xu Lei'],
             'arquivos': ['main Vol. 3.epub', 'main Vol. 4.epub', 'main Vol. 5.epub'], 'quantidade': 3,
             'titulos_alternativos': ['Daomu Biji Vol. 3', 'Daomu Biji Vol. 4', 'Daomu Biji Vol. 5']},
        ]}
        view = ce.presentation_obras(payload)
        row = next(row for row in view['obras'] if row['titulo'] == 'Daomu Biji')
        self.assertEqual(16, row['quantidade'])
        self.assertTrue(set(names).issubset({child['titulo'] for child in row['itens_serie']}))
        self.assertEqual(13, len(row['itens_serie']))
        self.assertEqual(16, len(row['arquivos']))
        self.assertEqual({'Série principal', 'Continuação', 'Prelúdio', 'História paralela', 'Especiais',
                          'Continuação / extra', 'Prelúdio / extra'},
                         {child['categoria'] for child in row['itens_serie']})
        self.assertIn('The Mystic Nine Extras', {child['titulo'] for child in row['itens_serie']})

    def test_visual_merge_preserves_files_not_listed_in_partial_details(self):
        payload = {'obras': [
            {'titulo': 'Sample Work', 'chave': 'sample_1', 'autores': ['Author'],
             'arquivos': ['volume-1.epub', 'volume-2.epub'], 'quantidade': 2,
             'itens_serie': [{'titulo': 'Sample Work Vol. 1', 'autores': ['Author'],
                              'arquivos': ['volume-1.epub']}]},
            {'titulo': 'Sample Work', 'chave': 'sample_2', 'autores': ['Author'],
             'arquivos': ['translation.epub'], 'quantidade': 1},
        ]}
        rows = ce.presentation_obras(payload)['obras']
        self.assertEqual(1, len(rows))
        self.assertEqual(3, rows[0]['quantidade'])
        self.assertEqual({'volume-1.epub', 'volume-2.epub', 'translation.epub'},
                         set(rows[0]['arquivos']))

    def test_explicitly_reported_translation_and_hash_aliases_group_visually(self):
        payload = {'obras': [
            {'chave': 'obra_00006', 'titulo': 'Система «Спаси Себя Сам»', 'autores': [], 'arquivos': ['ru.epub'], 'quantidade': 1},
            {'chave': 'obra_00066', 'titulo': 'ab0c4238', 'autores': [], 'arquivos': ['hash.epub'], 'quantidade': 1},
            {'chave': 'obra_00067', 'titulo': 'The Scum Villain’s Self-Saving System', 'autores': ['Mòxiāng Tóngxiù'], 'arquivos': ['en.epub'], 'quantidade': 1},
        ]}
        view = ce.presentation_obras(payload)
        self.assertEqual(1, len(view['obras']))
        self.assertEqual("The Scum Villain's Self-Saving System", view['obras'][0]['titulo'])
        self.assertEqual(3, view['obras'][0]['quantidade'])
        self.assertEqual({'ru.epub', 'hash.epub', 'en.epub'}, set(view['obras'][0]['arquivos']))

    def test_pasted_normalization_examples_keep_exact_aliases_and_fallbacks(self):
        key=lambda title, files=None: ce.presentation_title_key({'titulo':title,'arquivos':files or []})[0]
        self.assertEqual(key('No Moral'), key('No Moral SideStory 1-28'))
        self.assertEqual(key('No Moral'), key('No Moral Epilogue 1-17'))
        self.assertEqual(key('I Can Do It'), key('ICDI - 108 - 134 + extras'))
        self.assertEqual(key('Love Sea'), key('Love Sea [304-404].en'))
        self.assertEqual(key('Peerless'), key('Peerless (无双)'))
        russian='Система «Спаси Себя Сам» для главного злодея 1'
        from_title=key(russian)
        from_hash=key('ab0c42382ac2dee6e973d2fb1fd291eb', ['13745_Система_Спаси_Себя_Сам_для_главного_Z_Library.epub'])
        self.assertEqual(from_title, from_hash)

    def test_user_listed_series_groups_merge_only_the_named_work_ids(self):
        groups = {
            'KinnPorsche': [('obra_00079', 'VegasPete', 'vp.epub'),
                            ('obra_00080', 'KP & VP Special - Sprite Hoang', 'kp-vp.epub')],
            'Little Mushroom': [('obra_00127', 'Little Mushroom, Vol. 1', 'lm1.epub'),
                                ('obra_00128', 'Little Mushroom: Volume Two', 'lm2.epub')],
            "The Legendary Master's Wife": [
                ('obra_00083', "The Legendary Master's Wife - Book 7", 'lmw7.epub'),
                ('obra_00084', "The Legendary Master's Wife - Book 8", 'lmw8.epub')],
            'Tharntype': [('obra_00056', '[ENG] Tharntype Book 2', 'tt2.epub'),
                          ('obra_00057', '[ENG] Tharntype Book 1', 'tt1.epub')],
            "The Other World's Books Depend on the Bean Counter": [
                ('obra_00012', 'The Other World’s Books Depend on the Bean Counter, Vol. 2', 'ow2.epub'),
                ('obra_00013', 'The Other World’s Books Depend on the Bean Counter, Vol. 1', 'ow1.epub')],
            'Alabaster Penitentiary': [
                ('obra_00096', 'Fragments (Alabaster Penitentiary Book 4)', 'ap4.epub'),
                ('obra_00097', 'Brainwashed (Alabaster Penitentiary Book 3)', 'ap3.epub'),
                ('obra_00098', 'Joyless (Alabaster Penitentiary Book 2)', 'ap2.epub'),
                ('obra_00099', 'Distorted (Alabaster Penitentiary Book 1)', 'ap1.epub')],
            'Before the Coffee Gets Cold series': [
                ('obra_00031', 'Before the Coffee Gets Cold', 'coffee.epub'),
                ('obra_00032', 'Before Your Memory Fades', 'memory.epub')],
        }
        payload = {'obras': [
            {'chave': key, 'titulo': title, 'autores': ['Author'], 'arquivos': [file],
             'quantidade': 1, 'titulos_alternativos': []}
            for entries in groups.values() for key, title, file in entries
        ]}
        view = ce.presentation_obras(payload)['obras']
        self.assertEqual(set(groups), {row['titulo'] for row in view})
        for title, entries in groups.items():
            row = next(row for row in view if row['titulo'] == title)
            self.assertEqual(len(entries), row['quantidade'])
            self.assertEqual({entry[1] for entry in entries},
                             {child['titulo'] for child in row['itens_serie']})
            self.assertEqual({entry[2] for entry in entries}, set(row['arquivos']))


if __name__ == '__main__':
    unittest.main()

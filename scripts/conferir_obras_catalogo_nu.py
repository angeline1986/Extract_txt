#!/usr/bin/env python3
"""Compara obras da página Obras com o catálogo Novel Updates 0.1.5.

Por padrão, usa as obras exibidas na página Obras com verificação em
16/11/2026. Com --todos, percorre todas as obras atualmente exibidas na página
Obras. Compara título/autor com CSV e JSON e grava um CSV em tmp/. Os dois
arquivos do catálogo são conferidos entre si antes da busca.
"""
import argparse
import ast
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_epub_consolidar import presentation_obras  # noqa: E402


def read_json(path):
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f'{path} não contém uma lista JSON')
    return data


def parse_csv_cell(raw, expected):
    if expected is None:
        return None if raw == '' else raw
    if isinstance(expected, bool):
        if raw.lower() not in {'true', 'false'}:
            raise ValueError(f'Booleano inesperado no CSV: {raw!r}')
        return raw.lower() == 'true'
    if isinstance(expected, list):
        value = ast.literal_eval(raw) if raw else []
        if not isinstance(value, list):
            raise ValueError(f'Lista inesperada no CSV: {raw[:80]!r}')
        return value
    if isinstance(expected, int):
        if not raw:
            return None
        value = float(raw)
        return int(value) if value.is_integer() else value
    if isinstance(expected, float):
        return float(raw) if raw else None
    return raw


def read_catalog_pair(csv_path, json_path):
    json_rows = read_json(json_path)
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        csv_header = next(reader)
        csv_rows = list(reader)
    if len(csv_rows) != len(json_rows):
        raise ValueError(f'Contagens diferentes: CSV={len(csv_rows)}, JSON={len(json_rows)}')

    by_json = {str(row['id']): row for row in json_rows}
    id_column = csv_header.index('id')
    by_csv = {str(row[id_column]): row for row in csv_rows}
    if len(by_json) != len(json_rows) or len(by_csv) != len(csv_rows):
        raise ValueError('Há IDs ausentes ou repetidos no catálogo')
    if by_json.keys() != by_csv.keys():
        raise ValueError('Os conjuntos de IDs do CSV e JSON são diferentes')

    csv_fields = set(csv_header)
    json_fields = set().union(*(set(row) for row in json_rows))
    if csv_fields != json_fields:
        raise ValueError('O CSV e o JSON não têm o mesmo conjunto de campos')
    json_order = next(list(row.keys()) for row in json_rows if set(row) == json_fields)
    if set(json_order) != csv_fields:
        raise ValueError('Não foi possível determinar a ordem das colunas do JSON')

    compared = 0
    rows_using_json_order = 0
    differences = Counter()
    examples = []
    normalized_csv_by_id = {}
    for novel_id, jrow in by_json.items():
        cells = by_csv[novel_id]
        if len(cells) != len(csv_header):
            raise ValueError(f'Número de campos inesperado na linha CSV do ID {novel_id}')

        def compare_order(order):
            normalized = {}
            mismatches = []
            for position, field in enumerate(order):
                expected = jrow.get(field)
                raw = cells[position]
                try:
                    actual = parse_csv_cell(raw, expected)
                except (ValueError, SyntaxError):
                    actual = object()
                normalized[field] = actual
                if actual != expected:
                    mismatches.append((field, actual, expected))
            return normalized, mismatches

        header_result, header_mismatches = compare_order(csv_header)
        json_result, json_mismatches = compare_order(json_order)
        if len(json_mismatches) < len(header_mismatches):
            normalized, selected_mismatches = json_result, json_mismatches
            rows_using_json_order += 1
        else:
            normalized, selected_mismatches = header_result, header_mismatches
        normalized_csv_by_id[novel_id] = normalized
        for field, actual, expected in selected_mismatches:
            differences[field] += 1
            if len(examples) < 10:
                examples.append((novel_id, field, actual, expected))
        compared += 1
    return (json_rows, list(normalized_csv_by_id.values()), compared,
            rows_using_json_order, differences, examples)


def fold(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in value).split())


def title_keys(value):
    """Chaves para título literal e para um título sem rótulo de volume/edição."""
    raw = str(value or '').strip()
    if not raw:
        return []
    keys = [(fold(raw), 'literal')]
    core = re.sub(
        r'(?i)(?:\s*[-,:()]?\s*)(?:volume|vol\.?|book|part|pt\.?)\s*'
        r'(?:\d+|[ivxlcdm]+)(?:\s*[-,:].*)?\s*\)?$',
        '', raw,
    )
    core = re.sub(r'(?i)\s*[\[(](?:english edition|raw novel|complete|completed)[^\])]*[\])]\s*$', '', core)
    core = re.sub(r'(?i)\s+(?:english edition|raw novel)$', '', core).strip(' -_:,()[]')
    if core and fold(core) != fold(raw):
        keys.append((fold(core), 'base'))
    return [(key, kind) for key, kind in keys if key]


def author_variants(values):
    result = set()
    for raw in values:
        text = str(raw or '').strip()
        if not text:
            continue
        parts = [text]
        parts.extend(re.findall(r'\(([^()]*)\)', text))
        text = re.sub(r'\([^()]*\)', ' ', text)
        parts.extend(re.split(r'(?i)\s+and\s+|\s*[;,/&]\s*|\bpseudonym of\b', text))
        for part in parts:
            key = fold(part)
            if key:
                result.add(key)
    return result


def page_sample(manifest, selected_date=None):
    display = presentation_obras(manifest)
    confirmed_files = set()
    for work in manifest.get('obras', []):
        review = work.get('verificacao_obra') or {}
        country = str(review.get('nacionalidade_obra') or '').strip().casefold()
        if country and country not in {'pendente', 'não identificada', 'nao identificada', 'desconhecida', 'unknown'}:
            confirmed_files.update(review.get('epubs_lidos') or work.get('arquivos', []))

    visible = []
    for work in display.get('obras', []):
        files = set(map(str, work.get('arquivos', [])))
        work['nacionalidade_confirmada'] = bool(files) and files <= confirmed_files
        review = work.get('verificacao_obra') or {}
        if (not work['nacionalidade_confirmada']
                and (selected_date is None or review.get('verificado_em') == selected_date)):
            visible.append(work)
    return visible


def make_title_index(catalog):
    index = defaultdict(list)
    for row in catalog:
        novel_id = str(row['id'])
        for field in ('name', 'assoc_names'):
            values = [row.get(field, '')] if field == 'name' else (row.get(field) or [])
            for value in values:
                for key, quality in title_keys(value):
                    index[key].append((novel_id, field, quality, str(value)))
    return index


def find_matches(work, index, catalog_by_id):
    titles = list(dict.fromkeys(
        [work.get('titulo', '')] + list(work.get('titulos_alternativos') or [])
    ))
    candidates = {}
    for title in titles:
        for key, query_quality in title_keys(title):
            for novel_id, field, index_quality, catalog_title in index.get(key, []):
                score = (0 if field == 'name' else 2) + (0 if query_quality == index_quality == 'literal' else 1)
                found = candidates.get(novel_id)
                detail = (score, str(title), catalog_title, field)
                if found is None or detail[0] < found[0]:
                    candidates[novel_id] = detail

    work_author_names = [
        (work.get('verificacao_obra') or {}).get('autor', ''),
        *(work.get('autores') or []),
    ]
    work_authors = author_variants(work_author_names)
    results = []
    for novel_id, (score, title_used, catalog_title, field) in candidates.items():
        entry = catalog_by_id[novel_id]
        nu_authors = entry.get('authors') or []
        nu_author_keys = author_variants(nu_authors)
        author_match = bool(work_authors & nu_author_keys)
        if author_match:
            result = 'titulo_autor'
        elif nu_authors and work_authors:
            result = 'titulo_sem_autor_compativel'
        else:
            result = 'titulo_autor_indisponivel'
        results.append({
            'obra_id': work.get('chave', ''),
            'titulo_obra': work.get('titulo', ''),
            'autor_obra': (work.get('verificacao_obra') or {}).get('autor') or ' / '.join(work.get('autores') or []),
            'data_verificacao': (work.get('verificacao_obra') or {}).get('verificado_em', ''),
            'nacionalidade_obra': (work.get('verificacao_obra') or {}).get('nacionalidade_obra', ''),
            'resultado': result,
            'id_novelupdates': novel_id,
            'titulo_no_catalogo': entry.get('name', ''),
            'campo_titulo_correspondente': field,
            'titulo_que_correspondeu': catalog_title,
            'autor_no_catalogo': ' / '.join(nu_authors),
            'autor_compativel': 'sim' if author_match else 'não',
            'idioma_original_catalogo': entry.get('original_language', ''),
            'chave_de_titulo_usada': title_used,
            'referencias_obra': ' | '.join((work.get('verificacao_obra') or {}).get('referencias') or []),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'output/check_epub_obras.json')
    parser.add_argument('--csv', dest='csv_path', type=Path, default=ROOT / 'tmp/novels_0.1.5.csv')
    parser.add_argument('--json', dest='json_path', type=Path, default=ROOT / 'tmp/novels_0.1.5.json')
    parser.add_argument('--data', default='16/11/2026', help='Data exibida em Obras, formato dd/mm/aaaa')
    parser.add_argument('--todos', action='store_true', help='Percorre todas as obras atualmente exibidas na página Obras')
    parser.add_argument('--saida', type=Path, help='CSV de resultados; por padrão, grava em tmp/')
    args = parser.parse_args()
    selected_date = None
    if not args.todos:
        try:
            selected_date = datetime.strptime(args.data, '%d/%m/%Y').date().isoformat()
        except ValueError as exc:
            parser.error(f'Data inválida: {exc}')

    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    (catalog_json, catalog_csv, compared_rows, rows_using_json_order,
     catalog_differences, catalog_difference_examples) = read_catalog_pair(args.csv_path, args.json_path)
    sample = page_sample(manifest, selected_date)
    json_index = make_title_index(catalog_json)
    csv_index = make_title_index(catalog_csv)
    json_by_id = {str(row['id']): row for row in catalog_json}
    csv_by_id = {str(row['id']): row for row in catalog_csv}

    rows = []
    matching_catalogs = 0
    different_catalog_results = 0
    for work in sample:
        json_matches = find_matches(work, json_index, json_by_id)
        csv_matches = find_matches(work, csv_index, csv_by_id)
        json_match_ids = {match['id_novelupdates'] for match in json_matches}
        csv_match_ids = {match['id_novelupdates'] for match in csv_matches}
        catalogs_agree = json_match_ids == csv_match_ids
        matching_catalogs += catalogs_agree
        different_catalog_results += not catalogs_agree
        if json_matches or csv_matches:
            by_id_json = {match['id_novelupdates']: match for match in json_matches}
            by_id_csv = {match['id_novelupdates']: match for match in csv_matches}
            for novel_id in sorted(json_match_ids | csv_match_ids):
                result = by_id_json.get(novel_id) or by_id_csv[novel_id]
                result['encontrado_nos_catalogos'] = (
                    'CSV e JSON' if novel_id in json_match_ids and novel_id in csv_match_ids
                    else ('JSON' if novel_id in json_match_ids else 'CSV')
                )
                rows.append(result)
        else:
            review = work.get('verificacao_obra') or {}
            rows.append({
                'obra_id': work.get('chave', ''),
                'titulo_obra': work.get('titulo', ''),
                'autor_obra': review.get('autor') or ' / '.join(work.get('autores') or []),
                'data_verificacao': review.get('verificado_em', ''),
                'nacionalidade_obra': review.get('nacionalidade_obra', ''),
                'resultado': 'sem_correspondencia',
                'encontrado_nos_catalogos': 'nenhum',
                'id_novelupdates': '',
                'titulo_no_catalogo': '',
                'campo_titulo_correspondente': '',
                'titulo_que_correspondeu': '',
                'autor_no_catalogo': '',
                'autor_compativel': '',
                'idioma_original_catalogo': '',
                'chave_de_titulo_usada': '',
                'referencias_obra': ' | '.join(review.get('referencias') or []),
            })

    output_name = 'obras_todos_novelupdates.csv' if args.todos else f'obras_{args.data.replace("/", "-")}_novelupdates.csv'
    output = args.saida or ROOT / 'tmp' / output_name
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        'obra_id', 'titulo_obra', 'autor_obra', 'data_verificacao', 'nacionalidade_obra',
        'resultado', 'encontrado_nos_catalogos', 'id_novelupdates', 'titulo_no_catalogo', 'campo_titulo_correspondente',
        'titulo_que_correspondeu', 'autor_no_catalogo', 'autor_compativel',
        'idioma_original_catalogo', 'chave_de_titulo_usada', 'referencias_obra',
    ]
    with output.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)

    statuses = defaultdict(set)
    for row in rows:
        statuses[row['obra_id']].add(row['resultado'])
    exact = sum('titulo_autor' in result for result in statuses.values())
    title_only = sum(any(r.startswith('titulo_sem_autor') or r.startswith('titulo_autor_indisponivel') for r in result) for result in statuses.values())
    missing = sum(result == {'sem_correspondencia'} for result in statuses.values())
    if catalog_differences:
        print('CSV/JSON apresentam divergências após alinhar as linhas:')
        for field, count in catalog_differences.most_common():
            print(f'  {field}: {count:,} registros')
        for novel_id, field, csv_value, json_value in catalog_difference_examples[:5]:
            print(f'  Exemplo ID {novel_id}, {field}: CSV={csv_value!r}; JSON={json_value!r}')
    else:
        print(f'Conteúdo CSV/JSON equivalente: {compared_rows:,} registros e todos os campos.')
    if rows_using_json_order:
        print(f'Nota: {rows_using_json_order:,} linhas CSV foram alinhadas pela ordem dos campos JSON.')
    print(f'Resultados de busca CSV/JSON coincidem para: {matching_catalogs:,} de {len(sample):,} obras.')
    if different_catalog_results:
        print(f'Obras com resultados diferentes entre CSV e JSON: {different_catalog_results:,}.')
    if args.todos:
        print(f'Obras atualmente exibidas na página Obras: {len(sample):,}.')
    else:
        print(f'Obras da página Obras em {args.data}: {len(sample):,}.')
    print(f'Com título e autor compatíveis: {exact:,}.')
    print(f'Com título localizado, autor sem confirmação: {title_only:,}.')
    print(f'Sem correspondência de título: {missing:,}.')
    candidates = [row for row in rows if row['resultado'] != 'sem_correspondencia']
    for row in candidates:
        print(
            f"  {row['obra_id']} — {row['titulo_obra']} → "
            f"NU {row['id_novelupdates']} — {row['titulo_no_catalogo']} "
            f"(autor compatível: {row['autor_compativel'] or 'não'})"
        )
    print(f'Resultados salvos em: {output}')


if __name__ == '__main__':
    main()

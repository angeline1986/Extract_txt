#!/usr/bin/env python3
"""Classifica EPUBs usando dataset Novel Updates (shaido987/novel-dataset v0.1.5).
Dependencia: requests. Nao baixa EPUBs. Nao utiliza Google nem cache antigo.
"""
import argparse
import csv
import difflib
import json
import re
import sys
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path
from urllib.parse import quote
import requests

DATASET_URL = 'https://raw.githubusercontent.com/shaido987/novel-dataset/master/novels_0.1.5.csv'
LANG = {'chinese': 'CN', 'japanese': 'JP', 'korean': 'KR', 'thai': 'TH',
        'indonesian': 'ID', 'filipino': 'PH', 'malaysian': 'MY', 'khmer': 'KH'}
ADDED = ['titulo_normalizado', 'pais_origem', 'idioma_original', 'confianca',
         'status_verificacao', 'titulo_catalogo', 'autor_catalogo',
         'similaridade', 'fonte_verificacao', 'evidencia']

def key(s):
    s = unicodedata.normalize('NFKD', str(s or '').casefold())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace('_', ' ').replace('’', "'")
    return re.sub(r'[^\w\u3400-\u9fff\uac00-\ud7af]+', ' ', s).strip()

def title_from_filename(s):
    s = re.sub(r'\.epub$', '', s, flags=re.I).replace('_', ' ')
    s = re.sub(r'\([^)]*(?:\bcn\b|\bmtl\b|\bvol\b|\bchapters?\b|\b1lib\b)[^)]*\)', ' ', s, flags=re.I)
    s = re.sub(r'\b(?:chapters?\s*\d+|vol(?:ume)?\s*\d+|z.library.*|1lib.*)\b', ' ', s, flags=re.I)
    return re.sub(r'\s+', ' ', s).strip(' -.,')

def get_col(row, *names):
    normalized = {key(k).replace(' ', ''): v for k, v in row.items() if k}
    for n in names:
        v = normalized.get(key(n).replace(' ', ''))
        if v is not None:
            return str(v).strip()
    return ''

def aliases(value):
    if not value:
        return []
    try:
        obj = json.loads(value)
        if isinstance(obj, list):
            return [str(x) for x in obj if x]
    except (ValueError, TypeError):
        pass
    return [x.strip(' []\"\'') for x in re.split(r'\r?\n|\s*;\s*|\s*\|\s*', value) if x.strip()]

def load_catalog(path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('Catalogo sem cabecalho')
        print('Colunas do catalogo:', ', '.join(reader.fieldnames[:16]), flush=True)
        entries = []
        index = defaultdict(set)
        words = defaultdict(set)
        for row in reader:
            name = get_col(row, 'Name', 'Novel Name', 'Title')
            lang = get_col(row, 'Original Language', 'Original Langauge', 'Language')
            if not name or not lang:
                continue
            author = get_col(row, 'Author / Authors', 'Authors', 'Author')
            names = [name] + aliases(get_col(row, 'Associated Names', 'Alternative Names'))
            keys = set(filter(None, (key(n) for n in names)))
            if not keys:
                continue
            idx = len(entries)
            entries.append({'name': name, 'lang': lang, 'author': author, 'keys': keys})
            for k in keys:
                index[k].add(idx)
                for w in set(k.split()):
                    if len(w) >= 4:
                        words[w].add(idx)
        if not entries:
            raise ValueError('Catalogo sem obras reconhecidas; confira o formato CSV')
        return entries, index, words

def decide(title, entries, index, words):
    q = key(title)
    if not q:
        return None
    exact = index.get(q, set())
    if exact:
        candidates = [(1.0, i) for i in exact]
    else:
        tokens = [w for w in set(q.split()) if len(w) >= 4]
        ranked = Counter()
        for w in tokens:
            for i in words.get(w, ()):
                ranked[i] += 1
        pool = [i for i, _ in ranked.most_common(300)]
        candidates = []
        for i in pool:
            score = max(difflib.SequenceMatcher(None, q, a).ratio() for a in entries[i]['keys'])
            if score >= 0.78:
                candidates.append((score, i))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    score, idx = candidates[0]
    second = next((s for s, i in candidates[1:] if entries[i]['name'] != entries[idx]['name']), 0.0)
    ent = entries[idx]
    language = ent['lang']
    lang_key = key(language)
    code = next((v for k, v in LANG.items() if k in lang_key), '')
    unique = len({entries[i]['lang'] for s, i in candidates if s >= score - 0.005}) == 1
    # Apenas correspondencias exatas nao ambiguas sao classificadas automaticamente.
    confirmed = score == 1.0 and unique and bool(code)
    status = 'correspondencia_exata' if confirmed else 'revisar_correspondencia'
    return {'pais_origem': code if confirmed else 'INDEFINIDO',
            'idioma_original': language if confirmed else '',
            'confianca': 'alta' if confirmed else 'pendente',
            'status_verificacao': status,
            'titulo_catalogo': ent['name'], 'autor_catalogo': ent['author'],
            'similaridade': f'{score:.3f}',
            'fonte_verificacao': 'https://github.com/shaido987/novel-dataset/blob/master/novels_0.1.5.csv',
            'evidencia': ('Título exato no catálogo; idioma original: ' + language) if confirmed
                        else ('Candidato, confirmar título/autor; idioma candidato: ' + language +
                              ('' if score == 1.0 else f'; diferença de similaridade para 2º: {score-second:.3f}'))}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', type=Path, required=True)
    ap.add_argument('--saida', type=Path)
    ap.add_argument('--reset-json', action='store_true', help='Recria cache v3 do zero')
    ap.add_argument('--atualizar-catalogo', action='store_true')
    args = ap.parse_args()
    source = args.csv.expanduser().resolve()
    if not source.is_file():
        sys.exit(f'CSV não encontrado: {source}')
    dest = (args.saida or source.with_name(source.stem + '_origens_v3.csv')).resolve()
    catalog = source.parent / 'novels_0.1.5.csv'
    cachefile = source.parent / (source.stem + '_origens.v3.json')
    if args.atualizar_catalogo or not catalog.is_file():
        print('Baixando catálogo de novels (~19 MB), uma única vez...', flush=True)
        tmp = catalog.with_suffix('.csv.part')
        try:
            with requests.get(DATASET_URL, stream=True, timeout=(15, 90), headers={'User-Agent':'NovelCatalogLocal/3.0'}) as r:
                r.raise_for_status()
                with tmp.open('wb') as f:
                    for chunk in r.iter_content(1024 * 256):
                        if chunk:
                            f.write(chunk)
            if tmp.stat().st_size < 10000:
                raise ValueError('Download incompleto')
            tmp.replace(catalog)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            sys.exit(f'Falha no download do catálogo: {e}')
    entries, index, words = load_catalog(catalog)
    print(f'Catálogo: {len(entries)} obras; índice de títulos pronto.', flush=True)
    with source.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or 'nome_arquivo' not in reader.fieldnames:
            sys.exit('CSV sem coluna nome_arquivo')
        fields = list(dict.fromkeys(reader.fieldnames + ADDED))
        rows = [r for r in reader if (r.get('nome_arquivo') or '').lower().strip().endswith('.epub')]
    if args.reset_json:
        cache = {}
    else:
        try:
            cache = json.loads(cachefile.read_text(encoding='utf-8'))
            if not isinstance(cache, dict): cache = {}
        except (OSError, ValueError):
            cache = {}
    titles = {key(title_from_filename(r['nome_arquivo'])): title_from_filename(r['nome_arquivo']) for r in rows}
    print(f'EPUBs: {len(rows)}; títulos normalizados: {len(titles)}.', flush=True)
    for n, (k, title) in enumerate(titles.items(), 1):
        if k in cache: continue
        match = decide(title, entries, index, words)
        cache[k] = match or {'pais_origem':'INDEFINIDO','idioma_original':'',
                             'confianca':'nenhuma','status_verificacao':'nao_encontrado',
                             'titulo_catalogo':'','autor_catalogo':'','similaridade':'',
                             'fonte_verificacao':'','evidencia':'Não localizado no catálogo'}
        if n % 25 == 0 or n == len(titles):
            tmp = cachefile.with_suffix('.json.part')
            tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
            tmp.replace(cachefile)
            print(f'[{n}/{len(titles)}] processados', flush=True)
    # Salva também quando todos vieram do cache ou eram menos de 25.
    cachefile.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    counts = Counter()
    with dest.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            title = title_from_filename(row['nome_arquivo'])
            row.update(cache[key(title)])
            row['titulo_normalizado'] = title
            counts[row['status_verificacao']] += 1
            writer.writerow(row)
    print('Resultado:', dest)
    print('Cache novo:', cachefile)
    print('Resumo:', dict(counts))
    print('INDEFINIDO = não confirmado. Idioma original não prova nacionalidade do autor.')

if __name__ == '__main__':
    main()

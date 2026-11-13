#!/usr/bin/env python3
"""Check Epub — piloto de 5 obras. Novel Updates prioritário; MU/MD auxiliares.
Não modifica os EPUBs nem o CSV original. Sem confirmação inventada.
Requer Python 3.9+; somente biblioteca padrão.
"""
import argparse
import importlib.util
import csv
import difflib
import ast
from collections import defaultdict
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('/Volumes/Seagate2T/old/Check_Epub')
SOURCE = ROOT / 'output/telegram_midias_apenas_epub_origens_v3_ptbr.csv'
OUT = ROOT / 'output/piloto_metadados_5_epubs.csv'
CACHE = ROOT / 'cache/check_epub_piloto_consultas_v2.json'
IDS = ('95229', '95209', '95196', '95180', '95171')
NS = {'c': 'urn:oasis:names:tc:opendocument:xmlns:container',
      'opf': 'http://www.idpf.org/2007/opf',
      'dc': 'http://purl.org/dc/elements/1.1/'}
UA = 'Mozilla/5.0 (compatible; CheckEpubMetadataPilot/2.0; personal catalog research)'


def normalize(value):
    s = unicodedata.normalize('NFKD', str(value or '')).casefold()
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^\w]+', ' ', s).strip()


# Conversão opcional via OpenCC; sem a biblioteca, apenas equivalências verificadas.
# Nunca deduzir identidade da obra somente por coincidência de autor.
_AUTHOR_VARIANTS = str.maketrans({'爾': '尔', '黃': '黄', '陽': '阳', '貓': '猫', '蘇': '苏', '瑪': '玛'})
_OPENCC = None
if importlib.util.find_spec('opencc') is not None:
    try:
        from opencc import OpenCC
        _OPENCC = OpenCC('t2s')
    except (ImportError, RuntimeError, OSError):
        pass


def normalize_author(value):
    value = str(value or '')
    value = _OPENCC.convert(value) if _OPENCC else value.translate(_AUTHOR_VARIANTS)
    return normalize(value)


def normalized_language(value):
    raw = str(value or '').strip()
    lookup = {'chinese': ('zh', 'China'), 'japanese': ('ja', 'Japão'),
              'korean': ('ko', 'Coreia do Sul (a verificar)'),
              'thai': ('th', 'Tailândia'), 'indonesian': ('id', 'Indonésia'),
              'malay': ('ms', 'Malásia'), 'malaysian': ('ms', 'Malásia'),
              'filipino': ('fil', 'Filipinas'), 'khmer': ('km', 'Camboja')}
    code, country = lookup.get(normalize(raw), ('', ''))
    return code, country


def author_tokens(value):
    value = str(value or '').replace('<unknown>', '').strip()
    return [normalize_author(v) for v in re.split(r'\s+[|/\-]\s+', value) if normalize_author(v)]


def inspect_epub(path):
    result = {'titulo_epub': '', 'autor_epub': '', 'idioma_epub': '', 'erro_epub': ''}
    try:
        with zipfile.ZipFile(path) as z:
            container = ET.fromstring(z.read('META-INF/container.xml'))
            rootfile = container.find('.//c:rootfile', NS)
            if rootfile is None:
                raise ValueError('OPF não encontrado')
            opf = ET.fromstring(z.read(rootfile.attrib['full-path']))
            md = opf.find('opf:metadata', NS)
            if md is None:
                raise ValueError('Metadados OPF ausentes')
            for tag, field in [('title', 'titulo_epub'), ('creator', 'autor_epub'), ('language', 'idioma_epub')]:
                vals = [el.text.strip() for el in md.findall('dc:' + tag, NS) if el.text and el.text.strip()]
                result[field] = ' | '.join(dict.fromkeys(vals))
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        result['erro_epub'] = f'{type(exc).__name__}: {exc}'
    return result


def read_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        header = f.readline()
        f.seek(0)
        sep = ';' if header.count(';') >= header.count(',') else ','
        return list(csv.DictReader(f, delimiter=sep))


def fetch(url, payload=None):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/json;q=0.9,*/*;q=0.5',
        **({'Content-Type': 'application/json'} if data else {})})
    try:
        with urllib.request.urlopen(req, timeout=7) as response:
            return response.read(1_500_000).decode('utf-8', 'replace'), 'OK'
    except urllib.error.HTTPError as exc:
        return '', f'HTTP_{exc.code}'
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return '', f'ERRO_REDE_{type(exc).__name__}'


def candidate(title, author='', url='', status='CANDIDATO', detail=''):
    return {'status': status, 'titulo': title, 'autor': author, 'url': url, 'detalhe': detail}


def novelupdates(title, author):
    """Consulta busca pública; nunca transforma snippet em confirmação de ficha."""
    search_url = 'https://www.novelupdates.com/?' + urllib.parse.urlencode({'s': title, 'post_type': 'series'})
    body, state = fetch(search_url)
    result = candidate('', url=search_url, status='ERRO_CONSULTA' if state != 'OK' else 'NAO_CONFIRMADO', detail=state)
    if state != 'OK':
        return result
    # A busca do NU pode ser protegida por antibot; reconhecer páginas de desafio.
    if re.search(r'just a moment|checking your browser|captcha|cloudflare challenge', body, re.I):
        result.update(status='BLOQUEIO_ANTIBOT', detalhe='Busca protegida; não significa ausência')
        return result
    links = re.findall(r'href=["\'](https?://(?:www\.)?novelupdates\.com/series/[^"\'?#]+)', body, re.I)
    links = list(dict.fromkeys(html.unescape(x).rstrip('/') + '/' for x in links))
    # Só aceita candidato inequívoco quando o slug normalizado corresponde ao título.
    exact = []
    for link in links:
        slug = urllib.parse.unquote(urllib.parse.urlparse(link).path.strip('/').split('/')[-1]).replace('-', ' ')
        if normalize(slug) == normalize(title):
            exact.append(link)
    if len(exact) == 1:
        result.update(status='CANDIDATO_TITULO', titulo=title, url=exact[0], detalhe='Título compatível no NU; autor/origem requerem conferência da ficha')
    elif len(exact) > 1:
        result.update(status='AMBIGUO', detalhe='Múltiplas URLs compatíveis')
    else:
        result.update(status='SEM_CORRESPONDENCIA_CONFIRMADA', detalhe='Busca sem título exato detectável; não significa ausência')
    return result


def mangaupdates(title):
    search = 'https://www.mangaupdates.com/search.html?search=' + urllib.parse.quote(title)
    raw, state = fetch('https://api.mangaupdates.com/v1/series/search', {'search': title, 'perpage': 20})
    result = candidate('', url=search, status='ERRO_CONSULTA' if state != 'OK' else 'SEM_TITULO_EXATO', detail=state)
    if state != 'OK':
        return result
    try:
        records = []
        for hit in json.loads(raw).get('results', []):
            rec = hit.get('record') or {}
            names = [rec.get('title', '')]
            names += [a.get('title', '') for a in rec.get('associated', []) if isinstance(a, dict)]
            if normalize(title) in {normalize(n) for n in names if n}:
                records.append(rec)
        if len(records) == 1:
            rec = records[0]
            result.update(status='CANDIDATO_TITULO', titulo=rec.get('title', ''), url=rec.get('url') or search,
                          detalhe='Verificar se é a novel ou adaptação')
        elif len(records) > 1:
            result.update(status='AMBIGUO', detalhe=f'{len(records)} títulos iguais')
    except (ValueError, TypeError, AttributeError) as exc:
        result.update(status='RESPOSTA_INVALIDA', detalhe=type(exc).__name__)
    return result


def mangadex(title):
    url = 'https://api.mangadex.org/manga?' + urllib.parse.urlencode({'title': title, 'limit': 20})
    raw, state = fetch(url)
    result = candidate('', url='https://mangadex.org/search?q=' + urllib.parse.quote(title),
                       status='ERRO_CONSULTA' if state != 'OK' else 'SEM_TITULO_EXATO', detail=state)
    if state != 'OK':
        return result
    try:
        matches = []
        for item in json.loads(raw).get('data', []):
            attrs = item.get('attributes') or {}
            names = list((attrs.get('title') or {}).values())
            names += [v for obj in attrs.get('altTitles', []) for v in obj.values()]
            if normalize(title) in {normalize(n) for n in names if n}:
                matches.append((item, names))
        if len(matches) == 1:
            item, names = matches[0]
            result.update(status='CANDIDATO_TITULO', titulo=names[0],
                          url='https://mangadex.org/title/' + item['id'],
                          detalhe='Catálogo de quadrinhos; conferir adaptação')
        elif len(matches) > 1:
            result.update(status='AMBIGUO', detalhe=f'{len(matches)} títulos iguais')
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        result.update(status='RESPOSTA_INVALIDA', detalhe=type(exc).__name__)
    return result


def parse_values(value):
    """Decodifica listas JSON/Python e aliases separados por linhas."""
    value = str(value or '').strip()
    if not value:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            obj = parser(value)
            if isinstance(obj, (list, tuple)):
                return [str(x).strip() for x in obj if str(x).strip()]
        except (ValueError, SyntaxError, TypeError):
            pass
    return [x.strip() for x in re.split(r'\r?\n|\s*;\s*|\s*\|\s*', value) if x.strip()]


def get_catalog_field(row, *names):
    key = lambda v: re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(v)).casefold())
    norm = {key(k): str(v or '') for k, v in row.items() if k}
    return next((norm[key(n)] for n in names if norm.get(key(n))), '')


def build_local_catalog(rows):
    entries, exact_index, word_index, author_index = [], defaultdict(set), defaultdict(set), defaultdict(set)
    for row in rows:
        title = get_catalog_field(row, 'Name', 'name', 'Novel Name', 'Title')
        if not title:
            continue
        aliases = parse_values(get_catalog_field(row, 'Associated Names', 'assoc_names', 'Alternative Names'))
        author = get_catalog_field(row, 'Author / Authors', 'Authors', 'authors', 'Author')
        lang = get_catalog_field(row, 'Original Language', 'Original Langauge', 'Original Langauge\t', 'OriginalLanguage', 'original_language', 'Language of Origin', 'Language')
        keys = {normalize(x) for x in [title, *aliases] if normalize(x)}
        idx = len(entries)
        entries.append({'titulo': title, 'autor': author, 'idioma': lang, 'aliases': aliases, 'keys': keys})
        for a in parse_values(author):
            if normalize_author(a):
                author_index[normalize_author(a)].add(idx)
        for k in keys:
            exact_index[k].add(idx)
            for word in set(k.split()):
                if len(word) >= 4:
                    word_index[word].add(idx)
    return entries, exact_index, word_index, author_index


def local_nu_candidates(title, author, catalog, exact_index, word_index, author_index, previous_title=''):
    """Busca aliases e títulos; limita fuzzy a um conjunto pequeno de candidatos."""
    queries = list(dict.fromkeys(filter(None, (normalize(title), normalize(previous_title)))))
    ids = set()
    for q in queries:
        ids.update(exact_index.get(q, ()))
        for word in q.split():
            if len(word) >= 4:
                ids.update(word_index.get(word, ()))
    # Acrescenta obras do mesmo autor mesmo sem palavra comum no título.
    author_keys = {normalize_author(x) for x in author_tokens(author) if normalize_author(x)}
    for key in author_keys:
        ids.update(author_index.get(key, ()))
    # Fallback para títulos curtos sem tokens comuns no índice.
    if not ids:
        ids = set(range(len(catalog)))
    found = []
    for idx in ids:
        entry = catalog[idx]
        similarity = max((difflib.SequenceMatcher(None, q, k).ratio()
                          for q in queries for k in entry['keys']), default=0)
        exact = any(q in entry['keys'] for q in queries)
        if not exact and similarity < .57 and not (author_keys & {normalize_author(x) for x in parse_values(entry['autor'])}):
            continue
        known_authors = {normalize_author(x) for x in parse_values(entry['autor'])}
        known_authors.add(normalize_author(entry['autor']))
        author_match = bool(author_keys and known_authors and any(
            a == b or (len(a) >= 3 and len(b) >= 3 and (a in b or b in a))
            for a in author_keys for b in known_authors if a and b))
        score = round(100 * similarity + (12 if author_match else 0), 1)
        found.append({**entry, 'similaridade': round(similarity, 4),
                      'titulo_exato': exact, 'autor_confere': author_match, 'score': score})
    return sorted(found, key=lambda x: (-x['score'], -int(x['titulo_exato']), x['titulo']))[:3]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--online', action='store_true', help='Consultar sites; por padrão usa somente catálogo local e EPUB')
    ap.add_argument('--auxiliares', action='store_true', help='Consultar MangaUpdates e MangaDex (requer --online)')
    ap.add_argument('--refresh', action='store_true', help='Refaz consultas na rede')
    ap.add_argument('--base', type=Path, default=BASE, help='Pasta de EPUBs baixados')
    args = ap.parse_args()
    if not SOURCE.is_file():
        raise SystemExit(f'CSV de origem não encontrado: {SOURCE}')
    if not args.base.is_dir():
        raise SystemExit(f'Pasta de EPUBs não encontrada: {args.base}')
    original = {r.get('id_mensagem', '').strip(): r for r in read_csv(SOURCE)}
    epubs = list(args.base.rglob('*.epub'))
    cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
    local_path = ROOT / 'input/novels_0.1.5.csv'
    local_rows = read_csv(local_path) if local_path.exists() else []
    catalog, exact_index, word_index, author_index = build_local_catalog(local_rows)
    print('Colunas do catálogo:', ', '.join(local_rows[0].keys()) if local_rows else '(catálogo vazio)')
    print(f"Catálogo NU local: {len(catalog)} obras; {len(exact_index)} títulos/aliases indexados")
    output = []
    for mid in IDS:
        found = [p for p in epubs if p.name.startswith(mid + '_')]
        if len(found) != 1:
            print(f'[{mid}] AVISO: {len(found)} arquivos encontrados; ignorado')
            continue
        path = found[0]
        meta = inspect_epub(path)
        old = original.get(mid, {})
        title = re.sub(r'\s+Anthology\s*$', '', meta['titulo_epub'], flags=re.I).strip()
        title = title or old.get('titulo_normalizado', '') or path.stem.split('_', 1)[-1].replace('_', ' ')
        author = meta['autor_epub']
        if normalize(author) in ('unknown', 'desconhecido'):
            author = ''
        author = author or old.get('autor_catalogo', '')
        local = local_nu_candidates(title, author, catalog, exact_index, word_index, author_index, old.get("titulo_catalogo", ""))
        results = {}
        for name, fn in (('novelupdates', lambda: novelupdates(title, author)),
                         ('mangaupdates', lambda: mangaupdates(title)),
                         ('mangadex', lambda: mangadex(title))):
            key = f'{name}|{normalize(title)}'
            enabled = args.online and (name == 'novelupdates' or args.auxiliares)
            if not enabled:
                results[name] = candidate('', status='NAO_CONSULTADO')
            elif key in cache and not args.refresh and cache[key].get('status') not in ('BLOQUEIO_ANTIBOT', 'ERRO_CONSULTA', 'RESPOSTA_INVALIDA'):
                results[name] = cache[key]
            else:
                results[name] = fn()
                if results[name]['status'] not in ('BLOQUEIO_ANTIBOT', 'ERRO_CONSULTA', 'RESPOSTA_INVALIDA'):
                    cache[key] = results[name]
                    CACHE.parent.mkdir(parents=True, exist_ok=True)
                    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
                time.sleep(0.2)
        nu = results['novelupdates']
        # Um match por título não comprova identidade, país ou cidadania.
        # O Novel Updates prevalece; fontes auxiliares nunca bloqueiam sua identificação.
        if local and local[0]['titulo_exato'] and local[0]['autor_confere'] and (len(local) == 1 or local[0]['score'] > local[1]['score'] + 5):
            classification = 'CANDIDATO_NU_LOCAL_TITULO_EXATO_AUTOR_CONFERE'
        elif local and local[0]['titulo_exato']:
            classification = 'CANDIDATO_NU_LOCAL_TITULO_EXATO'
        elif local and local[0]['similaridade'] >= .85:
            classification = 'REVISAR_CANDIDATO_NU_LOCAL'
        elif nu['status'] == 'CANDIDATO_TITULO':
            classification = 'REVISAR_FICHA_NOVEL_UPDATES'
        else:
            classification = 'PENDENTE_NOVEL_UPDATES'
        original_language = local[0]['idioma'] if local and local[0]['titulo_exato'] else ''
        language_code, origin_hint = normalized_language(original_language)
        rec = {'id_mensagem': mid, 'arquivo': path.name, **meta,
               'titulo_pesquisado': title, 'autor_pesquisado': author,
               'titulo_catalogo_anterior': old.get('titulo_catalogo', ''),
               'autor_catalogo_anterior': old.get('autor_catalogo', ''),
               'pais_origem_anterior': old.get('pais_origem', ''),
               'status_anterior': old.get('status_verificacao', ''),
               'catalogo_local_matches': len(local),
               'catalogo_local_autor_confere': 'SIM' if local and local[0]['autor_confere'] else 'NAO',
               'catalogo_local_top3': json.dumps([{k: x[k] for k in ('titulo', 'autor', 'idioma', 'similaridade', 'titulo_exato', 'autor_confere')} for x in local], ensure_ascii=False),
               'idioma_original_catalogo': original_language,
               'codigo_idioma_original': language_code,
               'pais_origem_sugerido_por_idioma': origin_hint,
               'classificacao': classification,
               'pais_origem_confirmado': '', 'nacionalidade_autor_confirmada': '',
               'observacao': 'Novel Updates prioritário. Ausência em MU/MD não bloqueia. Nacionalidade exige evidência específica.'}
        for name, res in results.items():
            for field in ('status', 'titulo', 'autor', 'url', 'detalhe'):
                rec[f'{name}_{field}'] = res.get(field, '')
        output.append(rec)
        print(f'[{mid}] {title}\n  NU online: {nu["status"]} | MU: {results["mangaupdates"]["status"]} | MD: {results["mangadex"]["status"]}\n  Resultado: {classification}')
        if original_language:
            print(f'  Idioma original NU: {original_language} | origem sugerida: {origin_hint or "não determinada"}')
        for rank, item in enumerate(local, 1):
            print(f'  {rank}. {item["titulo"]} | autor={item["autor"]} | idioma={item["idioma"]} | título exato={item["titulo_exato"]} | autor confere={item["autor_confere"]} | similaridade={item["similaridade"]:.1%}')
    if not output:
        raise SystemExit('Nenhum dos 5 EPUBs encontrado; nada gravado')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0]), delimiter=';')
        writer.writeheader()
        writer.writerows(output)
    print(f'\nProcessados: {len(output)}/5\nRelatório: {OUT}\nOriginais preservados. Nenhuma nacionalidade presumida.')


if __name__ == '__main__':
    main()

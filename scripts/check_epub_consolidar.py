#!/usr/bin/env python3
"""Check EPUB: varredura local, deduplicação conservadora e painel HTML offline.
Uso: python3 check_epub_consolidar.py --projeto ~/Documents/TI/Projetos/Extract_txt --epubs /Volumes/Seagate2T/old/Check_Epub
Sem dependências externas; nunca altera EPUBs ou CSVs de origem.
"""
import argparse, csv, hashlib, html, json, re, shutil, sys, unicodedata, zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from xml.etree import ElementTree as ET

EXCLUDE = re.compile(r'(?i)(?:\b(?:vol(?:ume)?|chapters?|ch|cap(?:itulo)?|extras?|mtl|epub|pdf|z.library|1lib|chrysanthemum.garden)\b|\b(?:esp|ptbr)\b)')
URL_RE = re.compile(r'https?://[^\s<>"\'`\\]+', re.I)

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or '')).casefold()
    return ' '.join(re.findall(r'[a-z0-9]+', ''.join(c for c in s if not unicodedata.combining(c))))

def country_name(value):
    raw=str(value or '').strip()
    key=norm(raw)
    canonical={
        'japan':'Japão','japao':'Japão','japanese':'Japão','japonesa':'Japão',
        'china':'China','chinesa':'China','south korea':'Coreia do Sul','coreia do sul':'Coreia do Sul','sul coreana':'Coreia do Sul',
        'united states':'Estados Unidos','united states of america':'Estados Unidos','estados unidos':'Estados Unidos','estadunidense':'Estados Unidos',
        'thailand':'Tailândia','tailandia':'Tailândia','tailandesa':'Tailândia',
        'canada':'Canadá','canadense':'Canadá',
        'united kingdom':'Reino Unido','reino unido':'Reino Unido','britanica':'Reino Unido','britanico':'Reino Unido',
        'italy':'Itália','italia':'Itália','italiana':'Itália',
        'denmark':'Dinamarca','dinamarca':'Dinamarca','dinamarquesa':'Dinamarca',
        'australia':'Austrália','australiana':'Austrália',
        'philippines':'Filipinas','filipinas':'Filipinas','mexico':'México','mexicana':'México',
        'russia':'Rússia','russa':'Rússia','ireland':'Irlanda','irlanda':'Irlanda','irlandesa':'Irlanda',
        'singapore':'Singapura','singapura':'Singapura','sweden':'Suécia','suecia':'Suécia',
        'spain':'Espanha','espanha':'Espanha','chile':'Chile','taiwan':'Taiwan',
        'new zealand':'Nova Zelândia','nova zelandia':'Nova Zelândia',
        'czech republic':'República Tcheca','republica tcheca':'República Tcheca','india':'Índia'
    }
    return canonical.get(key,raw)

CHEONCHUSEIN_ID='72590'
CHEONCHUSEIN_KEY='obra_01422'
CHEONCHUSEIN_FILE='72590_For a Thousand Autums - Lanmaru.epub'
CHEONCHUSEIN_TITLE='For a Thousand Autumns'
CHEONCHUSEIN_NU='https://www.novelupdates.com/series/celestial/'
CHEONCHUSEIN_MANTA='https://manta.net/en/series/for-a-thousand-autumns-full-ver?seriesId=3467'
CHEONCHUSEIN_MANHWA='https://mangabaka.org/manhwa/92028/For-a-Thousand-Autumns'
CHEONCHUSEIN_AUTHORS='Lanmaru (novel), Gilmong e Boogie (arte)'
CHEONCHUSEIN_PROTAGONISTS=['Moonpyeong Seok','Demônio Celestial']
CHEONCHUSEIN_ORIGINAL='Cheonchusein (천추세인)'
CHEONCHUSEIN_SYNOPSIS='Um membro de baixo escalão da Seita Demoníaca vira guarda-costas do líder em uma disputa de sucessão.'
ZHICHU_SURVIVORSHIP_ID='79462'
ZHICHU_SURVIVORSHIP_KEY='obra_01741'
ZHICHU_AUTHOR='稚楚 (Zhichu)'

def is_cheonchusein_item(item):
    ids={str(value).strip() for value in item.get('ids',[]) if str(value).strip()}
    ids.add(str(item.get('id','')).strip())
    files=[Path(value).name for value in item.get('arquivos',[]) if value]
    if item.get('nome'):files.append(Path(str(item['nome'])).name)
    return CHEONCHUSEIN_ID in ids or any(name.startswith(CHEONCHUSEIN_ID+'_') for name in files)

def apply_cheonchusein_work(work):
    if not is_cheonchusein_item(work):return
    work.update({
        'chave':CHEONCHUSEIN_KEY,
        'titulo':CHEONCHUSEIN_TITLE,
        'titulos_alternativos':[CHEONCHUSEIN_ORIGINAL,'Celestial'],
        'autores':['Lanmaru'],
        'identificada':True,
        'nacionalidade_conhecida':True,
        'tem_link_nu':True,
        'titulo_original_obra':CHEONCHUSEIN_ORIGINAL,
        'tipo_obra':'Manhwa / Webtoon',
        'sinopse_obra':CHEONCHUSEIN_SYNOPSIS,
    })
    review=work.setdefault('verificacao_obra',{})
    review.update({
        'autor':CHEONCHUSEIN_AUTHORS,
        'nacionalidade_obra':'Coreia do Sul',
        'protagonistas':CHEONCHUSEIN_PROTAGONISTS,
        'titulo_original_obra':CHEONCHUSEIN_ORIGINAL,
        'tipo_obra':'Manhwa / Webtoon',
        'sinopse_obra':CHEONCHUSEIN_SYNOPSIS,
        'referencias':[CHEONCHUSEIN_MANTA,CHEONCHUSEIN_MANHWA,CHEONCHUSEIN_NU],
        'fonte_nacionalidade':CHEONCHUSEIN_NU,
        'criterio_nacionalidade':'Novel Updates cataloga Celestial (천추세인) como obra coreana de Lanmaru; Manta identifica a adaptação For a Thousand Autumns e descreve Moonpyeong Seok e o Demônio Celestial.',
        'metodo':'Conferência da ficha de Celestial no Novel Updates e da página da adaptação no Manta; EPUB local associado ao ID 72590.',
        'verificado_em':'2026-11-17',
        'epubs_lidos':[CHEONCHUSEIN_FILE],
        'epubs_nao_lidos':[],
    })

def apply_cheonchusein_record(record):
    if str(record.get('id','')).strip()!=CHEONCHUSEIN_ID:return
    record.update({
        'titulo':CHEONCHUSEIN_TITLE,
        'catalogo':CHEONCHUSEIN_TITLE,
        'autor':'Lanmaru',
        'idioma':'korean',
        'pais':'KR',
        'nacionalidade_obra':'Coreia do Sul',
        'fonte_nacionalidade_obra':CHEONCHUSEIN_NU,
        'referencia_obra':CHEONCHUSEIN_MANTA,
        'status_catalogo':'identificado',
        'evidencia_catalogo':'Identidade revisada: For a Thousand Autumns (Cheonchusein / Celestial), adaptação coreana distinta da novel chinesa Thousand Autumns / Qian Qiu.',
        'obra_verificada':CHEONCHUSEIN_TITLE,
        'obra_chave':CHEONCHUSEIN_KEY,
        'autor_obra':CHEONCHUSEIN_AUTHORS,
        'protagonistas_obra':CHEONCHUSEIN_PROTAGONISTS,
        'titulo_original_obra':CHEONCHUSEIN_ORIGINAL,
        'tipo_obra':'Manhwa / Webtoon',
        'sinopse_obra':CHEONCHUSEIN_SYNOPSIS,
        'localizada_em':'Novel Updates / Manta',
        'verificadas':'17/11/2026',
    })

def is_zhichu_survivorship_item(item):
    ids={str(value).strip() for value in item.get('ids',[]) if str(value).strip()}
    ids.add(str(item.get('id','')).strip())
    files=[Path(value).name for value in item.get('arquivos',[]) if value]
    if item.get('nome'):files.append(Path(str(item['nome'])).name)
    return (ZHICHU_SURVIVORSHIP_ID in ids or
            str(item.get('chave',''))==ZHICHU_SURVIVORSHIP_KEY or
            any(name.startswith(ZHICHU_SURVIVORSHIP_ID+'_') for name in files))

def apply_zhichu_survivorship_work(work):
    if not is_zhichu_survivorship_item(work):return
    work['autores']=[ZHICHU_AUTHOR]
    review=work.setdefault('verificacao_obra',{})
    review['autor']=ZHICHU_AUTHOR

def apply_zhichu_survivorship_record(record):
    if str(record.get('id','')).strip()!=ZHICHU_SURVIVORSHIP_ID:return
    record['autor']=ZHICHU_AUTHOR
    record['autor_obra']=ZHICHU_AUTHOR

VERIFIED_TITLE_RECORD_IDS={
    '55067','92142','75152','74733','60264',
    '52701','52702','52703','52704','38644','38645','38646','38647',
    '66126','83823',
}

def apply_verified_title_corrections(record):
    record_id=str(record.get('id','')).strip()
    if record_id not in VERIFIED_TITLE_RECORD_IDS:return False
    if record_id=='55067':
        record.update({
            'catalogo':'The Dangerous Convenience Store','autor':'945','idioma':'korean','pais':'KR',
            'status_catalogo':'identificado',
            'evidencia_catalogo':'Correção de correspondência: The Dangerous Convenience Store é a obra coreana de 945; não corresponde a The Wild Deer Convenience Store, de Xu Weijüquan.',
            'obra_verificada':'The Dangerous Convenience Store','obra_chave':'obra_01805',
            'autor_obra':'945','nacionalidade_obra':'Coreia do Sul',
            'protagonistas_obra':['Yeo Eui-joon','Gunwoo'],'tipo_obra':'Manhwa / Webtoon',
            'fonte_nacionalidade_obra':'https://www.lezhinus.com/en/comic/dangerous_store',
            'referencia_obra':'https://www.lezhinus.com/en/comic/dangerous_store',
            'localizada_em':'Lezhin Comics','verificadas':'17/11/2026',
        })
    elif record_id in {'92142','75152','74733','60264'}:
        record.update({
            'catalogo':'There’s Something Wrong with the Chief: Du Zhu You Bing',
            'autor':'Yang Su (杨溯)','idioma':'chinese','pais':'CN','status_catalogo':'identificado',
            'evidencia_catalogo':'Correção de correspondência: obra de Yang Su; não corresponde a There’s Something Wrong With This Account, de Kindergarten Expert.',
            'obra_verificada':'There’s Something Wrong with the Chief: Du Zhu You Bing',
            'autor_obra':'Yang Su (杨溯)','nacionalidade_obra':'China',
            'protagonistas_obra':['Xiahou Lian','Xie Jinglan'],
            'fonte_nacionalidade_obra':'https://sevenseasentertainment.com/series/theres-something-wrong-with-the-chief-du-zhu-you-bing-novel/',
            'referencia_obra':'https://sevenseasentertainment.com/series/theres-something-wrong-with-the-chief-du-zhu-you-bing-novel/',
            'localizada_em':'Seven Seas','verificadas':'17/11/2026',
        })
    elif record_id in {'52701','52702','52703','52704','38644','38645','38646','38647'}:
        record.update({
            'catalogo':'Rose and Renaissance','autor':'Zhichu (稚楚)','idioma':'chinese','pais':'CN',
            'status_catalogo':'identificado',
            'evidencia_catalogo':'Título e autoria confirmados no registro da obra original; autora Zhichu (稚楚).',
            'obra_verificada':'Rose and Renaissance','obra_chave':'obra_00943',
            'autor_obra':'Zhichu (稚楚)','nacionalidade_obra':'China',
            'protagonistas_obra':['Xia Xiqing (夏习清)','Zhou Ziheng (周自珩)'],
            'fonte_nacionalidade_obra':'https://www.jjwxc.net/onebook.php?novelid=3828175',
            'referencia_obra':'https://books.google.com/books/about/Rose_and_Renaissance_Volume_1.html?id=QvKTzwEACAAJ',
            'localizada_em':'JJWXC / Google Books','verificadas':'17/11/2026',
        })
    elif record_id=='66126':
        record.update({
            'catalogo':'Tokyo Ghoul','autor':'Sui Ishida','idioma':'japanese','pais':'JP',
            'status_catalogo':'identificado',
            'evidencia_catalogo':'Identidade e autoria confirmadas pela página oficial da VIZ; Sui Ishida nasceu no Japão.',
            'obra_verificada':'Tokyo Ghoul','obra_chave':'obra:tokyo-ghoul',
            'autor_obra':'Sui Ishida','nacionalidade_obra':'Japão','tipo_obra':'Mangá',
            'fonte_nacionalidade_obra':'https://www.viz.com/tokyo-ghoul',
            'referencia_obra':'https://www.viz.com/tokyo-ghoul',
            'localizada_em':'VIZ','verificadas':'17/11/2026',
        })
    elif record_id=='83823':
        record.update({
            'catalogo':'Doll (人偶)','autor':'Ali Rabbit (阿哩兔)','idioma':'chinese','pais':'CN',
            'status_catalogo':'identificado','obra_verificada':'Doll (人偶)',
            'autor_obra':'Ali Rabbit (阿哩兔)','nacionalidade_obra':'China','obra_chave':'obra_01954',
            'tipo_obra':'Web novel','fonte_nacionalidade_obra':'https://www.novelupdates.com/series/doll/',
            'referencia_obra':'https://www.novelupdates.com/series/doll/',
            'localizada_em':'Novel Updates','verificadas':'17/11/2026',
        })
    return True

def apply_verified_title_corrections_work(work):
    ids={str(value).strip() for value in work.get('ids',[]) if str(value).strip()}
    ids.update(match.group(1) for filename in work.get('arquivos',[])
               if (match:=re.match(r'^(\d{1,9})[_\s-]',Path(str(filename)).name)))
    for record_id in ids:
        correction={'id':record_id}
        if not apply_verified_title_corrections(correction):continue
        title=correction.get('obra_verificada')
        author=correction.get('autor_obra')
        country=correction.get('nacionalidade_obra')
        source=correction.get('fonte_nacionalidade_obra','')
        work.update({'chave':correction.get('obra_chave',work.get('chave','')),
                     'titulo':title,'autores':[author] if author else work.get('autores',[]),
                     'identificada':True,'nacionalidade_conhecida':bool(country)})
        review=work.setdefault('verificacao_obra',{})
        review.update({'autor':author,'nacionalidade_obra':country,
                       'protagonistas':correction.get('protagonistas_obra',review.get('protagonistas',[])),
                       'referencias':[correction.get('referencia_obra','')] if correction.get('referencia_obra') else [],
                       'fonte_nacionalidade':source,
                       'criterio_nacionalidade':correction.get('evidencia_catalogo',''),
                       'metodo':'Correção de identidade e origem baseada em referência editorial ou ficha da obra original.',
                       'verificado_em':'2026-11-17'})
        if correction.get('tipo_obra'):
            review['tipo_obra']=correction['tipo_obra']
        return

def title_guess(name):
    s=Path(name).stem
    s=re.sub(r'^\d{4,9}[_\s-]+','',s)
    s=s.replace('_',' ')
    s=re.sub(r'(?i)\b(?:vol(?:ume)?\.?\s*\d+|ch(?:apters?)?\.?\s*\d+(?:\s*[-–]\s*\d+)?|cap(?:itulo)?\.?\s*\d+)\b.*$','',s)
    s=re.sub(r'(?i)\s*[-–]\s*(?:chrysanthemum garden|mtl|z.library|enju|wu zhe)\b.*$','',s)
    return re.sub(r'\s+',' ',s).strip(' -_.,') or Path(name).stem

def load_csv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:
        first=f.readline();f.seek(0)
        return list(csv.DictReader(f,delimiter=';' if first.count(';')>first.count(',') else ','))

def find_epubs(root):
    if not root or not root.exists(): return []
    return sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.lower()=='.epub' and not p.name.startswith('._')),key=lambda p:str(p))

def identification_source(url):
    raw=str(url or '').strip()
    parsed=urlparse(raw)
    host=parsed.netloc.lower().split(':')[0]
    host=host.removeprefix('www.')
    known={
        'novelupdates.com':'Novel Updates',
        'jjwxc.net':'JJWXC',
        'ridibooks.com':'RIDI Books',
        'sevenseasentertainment.com':'Seven Seas',
        'yenpress.com':'Yen Press',
        'penguinrandomhouse.com':'Penguin Random House',
        'goodreads.com':'Goodreads',
        'fable.co':'Fable',
        'books.google.com':'Google Books',
        'google.com':'Google Books',
        'mebmarket.com':'MEB Market',
        'fanqienovel.com':'Fanqie Novel',
        'webnovel.com':'Webnovel',
        'wattpad.com':'Wattpad',
        'tunwalai.com':'Tunwalai',
        'tappytoon.com':'Tappytoon',
        'wtr-lab.com':'WTR-Lab',
        'marinetl.xyz':'MarineTL',
        'chrysanthemumgarden.com':'Chrysanthemum Garden',
        'kadokawa-anime.com':'KADOKAWA',
        'mementobl.com':'MeMento',
        'vialactea.ca':'Via Lactea',
        'github.com':'Catálogo de obras',
    }
    for domain,label in known.items():
        if host==domain or host.endswith('.'+domain):return label
    if not host:return raw
    if host.endswith('wordpress.com'):
        return host.split('.')[0].replace('-',' ').title()+' (WordPress)'
    return host.removeprefix('m.').replace('-',' ').title()

def verification_display(value):
    """Format timestamps for the HTML without inventing midnight for date-only values."""
    raw=str(value or '').strip()
    if not raw:return 'Pendente'
    match=re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}):(\d{2}))?',raw)
    if not match:return raw
    date=f'{match.group(3)}/{match.group(2)}/{match.group(1)}'
    return date+(f' {match.group(4)}:{match.group(5)}:{match.group(6)}' if match.group(4) else '')

def extract_epub(p):
    out={'arquivo':p.name,'caminho':str(p),'tamanho':p.stat().st_size,'sha256':'','titulo':'','autores':[], 'idioma':'','identificadores':[], 'links':[], 'erro':''}
    try:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        out['sha256']=h.hexdigest()
        links=set()
        with zipfile.ZipFile(p) as z:
            members=z.namelist(); opf=[]
            for name in members:
                if name.lower().endswith('.opf'):
                    opf.append(name)
                    try:
                        tree=ET.fromstring(z.read(name))
                        for el in tree.iter():
                            tag=el.tag.rsplit('}',1)[-1].lower()
                            value=(el.text or '').strip()
                            if tag=='title' and value and not out['titulo']:out['titulo']=value
                            elif tag=='creator' and value:out['autores'].append(value)
                            elif tag=='language' and value and not out['idioma']:out['idioma']=value
                            elif tag=='identifier' and value:out['identificadores'].append(value)
                    except (ET.ParseError,ValueError):pass
            for name in members:
                if not name.lower().endswith(('.opf','.xhtml','.html','.htm','.ncx')):continue
                info=z.getinfo(name)
                if info.file_size>8*1024*1024:continue
                try:content=z.read(name).decode('utf-8','replace').replace('&amp;','&')
                except (OSError,RuntimeError):continue
                for m in URL_RE.finditer(content):
                    u=html.unescape(m.group(0)).rstrip('.,;)]}')
                    if len(u)<1000 and urlparse(u).netloc:links.add(u)
        out['links']=sorted(links)
    except (OSError,zipfile.BadZipFile,RuntimeError,ValueError) as e:out['erro']=type(e).__name__+': '+str(e)[:180]
    return out

def candidates_lookup(root):
    p=root/'novelupdates_candidatos.json'
    if not p.exists():return {}
    try:
        raw=json.loads(p.read_text(encoding='utf-8'))
        if isinstance(raw,dict):raw=raw.get('resultados',raw.get('registros',[]))
        return {str(x.get('id_mensagem','')):x for x in raw if isinstance(x,dict)}
    except (ValueError,OSError):return {}


# CHECK_EPUB_OBRAS_V2
_VOLUME_MARKER = re.compile(r'(?i)\b(?:vol(?:ume)?\.?\s*[-_#:]?\s*\d+|livro\s*\d+|tomo\s*\d+|chapter\s*\d+(?:\s*[-–]\s*\d+)?|ch\.?\s*\d+(?:\s*[-–]\s*\d+)?)\b')
_GENERIC = {'', 'unknown', 'none', 'null', 'na', 'n a', 'desconhecido',
            'indefinido', 'nao informado', 'nao identificada', 'untitled',
            'ebook', 'epub', 'author', 'unknown author', 'epubpress'}

def is_sidecar(record):
    """AppleDouble resource-fork files are filesystem metadata, not EPUB books."""
    return Path(record.get('arquivo', '')).name.startswith('._')

def clean_identity(value):
    value = re.sub(r'^\d{4,9}[_\s-]+', '', str(value or ''))
    value = re.sub(r'(?i)\s*[-–]\s*(?:chrysanthemum garden|mtl|z\.library|enju|wu zhe)\b.*$', '', value)
    value = _VOLUME_MARKER.sub(' ', value)
    return norm(value).strip()

def trustworthy(value):
    key = norm(value)
    raw = str(value or '').strip()
    return bool(key and key not in _GENERIC and not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f-]{27,}', raw, re.I))

def trusted_work_ids(record):
    """Read only explicit OPF identifier metadata; body links can be ads."""
    result = set()
    for raw in record.get('identificadores', []):
        value = str(raw or '').strip()
        parsed = urlparse(value)
        host = parsed.netloc.lower().removeprefix('www.')
        if host == 'novelupdates.com' and re.fullmatch(r'/series/[a-z0-9-]+/?', parsed.path, re.I):
            result.add('nu:' + parsed.path.rstrip('/').lower())
        elif host == 'jjwxc.net' and parsed.path.lower().endswith(('onebook.php', 'bookdetail.php')):
            novel_id = parse_qs(parsed.query).get('novelid', [])
            if len(novel_id) == 1 and novel_id[0].isdigit():
                result.add('jjwxc:' + novel_id[0])
    return result

def volume_key(record):
    """Título-base apenas quando o nome declara explicitamente um volume."""
    name = Path(record.get('arquivo', '')).stem
    if not _VOLUME_MARKER.search(name):
        return ''
    title = record.get('titulo', '')
    base = clean_identity(title) if trustworthy(title) else clean_identity(title_guess(name))
    return base if len(base) >= 4 else ''

def consolidate_volumes(groups):
    """Merge only explicitly numbered volumes with the same title base."""
    buckets = defaultdict(list)
    for key, records in groups.items():
        bases = {volume_key(r) for r in records if volume_key(r)}
        if len(bases) == 1:
            buckets[next(iter(bases))].append(key)
    for base, keys in buckets.items():
        if len(keys) < 2:
            continue
        clusters = []
        for key in keys:
            authors = {norm(a) for r in groups[key]
                       for a in (r.get('autores') or []) if trustworthy(a)}
            authors.update(norm(r.get('autor_catalogo')) for r in groups[key]
                           if trustworthy(r.get('autor_catalogo')))
            ids = set().union(*(trusted_work_ids(r) for r in groups[key]))
            cluster = next((c for c in clusters
                            if (not authors or not c['authors'] or authors == c['authors'])
                            and (not ids or not c['ids'] or ids == c['ids'])), None)
            if cluster:
                cluster['keys'].append(key); cluster['authors'].update(authors); cluster['ids'].update(ids)
            else:
                clusters.append({'keys': [key], 'authors': authors, 'ids': ids})
        for cluster in clusters:
            chosen = cluster['keys'][0]
            for key in cluster['keys'][1:]:
                groups[chosen].extend(groups.pop(key))
    return groups

def nationality_known(row):
    """Só considera valores explícitos; idioma do próprio EPUB não basta."""
    placeholders = {'', '-', 'n/a', 'na', 'none', 'null', 'unknown', 'unk',
                    'desconhecido', 'indefinido', 'nao identificado',
                    'nao identificada', 'nao informado', 'pendente',
                    'a identificar', 'indefinida'}
    return bool(norm(row.get('pais_origem', '')) not in placeholders)

def grouping(records):
    """Conservative grouping: exact file hash, exact title+author, or safe volume base."""
    groups={}; bysha={}; bytitle={}
    for r in records:
        if is_sidecar(r):
            continue
        key=None; sha=r.get('sha256','')
        raw_title = r.get('titulo') or title_guess(r.get('arquivo',''))
        title = clean_identity(raw_title) if trustworthy(raw_title) else ''
        authors = {norm(a) for a in r.get('autores',[]) if trustworthy(a)}
        authors.update(norm(r.get('autor_catalogo')) for _ in [0] if trustworthy(r.get('autor_catalogo')))
        author = tuple(sorted(authors))
        ids=trusted_work_ids(r)
        def compatible(existing):
            known_ids=set().union(*(trusted_work_ids(x) for x in existing))
            known_authors={norm(a) for x in existing for a in x.get('autores',[]) if trustworthy(a)}
            known_authors.update(norm(x.get('autor_catalogo')) for x in existing if trustworthy(x.get('autor_catalogo')))
            same_namespace_conflict = any(
                {value for value in ids if value.startswith(namespace)}
                and {value for value in known_ids if value.startswith(namespace)}
                and {value for value in ids if value.startswith(namespace)} != {value for value in known_ids if value.startswith(namespace)}
                for namespace in ('nu:', 'jjwxc:')
            )
            return not (ids and known_ids and ids.isdisjoint(known_ids)) and not same_namespace_conflict and not (authors and known_authors and authors != known_authors)
        for id_ in ids:
            idkey=('id',id_)
            if idkey in bytitle:
                prior=groups[bytitle[idkey]]
                prior_titles={clean_identity(x.get('titulo') or title_guess(x.get('arquivo',''))) for x in prior}
                prior_titles.discard('')
                if (not title or not prior_titles or title in prior_titles) and compatible(prior):
                    key=bytitle[idkey];break
        if key is None and sha and sha in bysha:key=bysha[sha]
        volume = volume_key(r)
        identity_title = volume or title
        if key is None and identity_title and author and (identity_title,author) in bytitle:
            candidate=bytitle[(identity_title,author)]
            if compatible(groups[candidate]):key=candidate
        if key is None and volume:
            # Volumes may omit an author; only join when no known metadata conflicts.
            for existing_key, existing in groups.items():
                if any(volume_key(x)==volume for x in existing):
                    known_authors={norm(a) for x in existing for a in x.get('autores',[]) if trustworthy(a)}
                    if not authors or not known_authors or authors == known_authors:
                        key=existing_key;break
        if key is None:key='obra_'+str(len(groups)+1).zfill(5);groups[key]=[]
        groups[key].append(r)
        if sha:bysha[sha]=key
        if identity_title and author:bytitle[(identity_title,author)]=key
        for id_ in ids:bytitle[('id',id_)]=key
    return groups

def safe_json(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')

_PRESENTATION_VOLUME = re.compile(r'(?i)\b(?:vol(?:ume)?\.?|book|livro|part|pt|tomo|band|bd\.?|v\.?)\s*[-_#:]?\s*(\d+)\b')
_PRESENTATION_CHAPTER_RANGE = re.compile(r'(?i)(?:#?\s*\d+\s*[-–]\s*#?\s*\d+|\b(?:ch|chapter|chapters|c)\.?\s*\d+(?:\s*(?:to|[-–])\s*\d+)?)')
_PRESENTATION_ALIASES = {
    'icdi':'I Can Do It', 'i can do it':'I Can Do It', 'i can do it icdi':'I Can Do It',
    'daomu biji':'Daomu Biji', 'the grave robbers chronicles':'Daomu Biji',
    'lout of counts family':"Trash of the Count's Family",
    'trash of the counts family':"Trash of the Count's Family",
    'lie huo jiao chou':'Drowning Sorrows in Raging Fire',
    'drowning sorrows in raging fire':'Drowning Sorrows in Raging Fire',
    'sha po lang':'Stars of Chaos', 'stars of chaos':'Stars of Chaos',
    'qian qiu':'Thousand Autumns', 'thousand autumns':'Thousand Autumns',
    'wuchang jie':'Wu Chang Jie', 'wu chang jie':'Wu Chang Jie',
    'heavenly official blessing':"Heaven Official's Blessing",
    'heaven officials blessing':"Heaven Official's Blessing",
    'the scum villains self saving system':"The Scum Villain's Self-Saving System",
    'система спаси себя сам для главного злодея':"The Scum Villain's Self-Saving System",
    'система спаси себя сам для главного':"The Scum Villain's Self-Saving System",
    'istoriya bolezni':'Case File Compendium', 'история болезни':'Case File Compendium',
    'medical record book case file compendium':'Case File Compendium',
    'case file compendium bing an ben':'Case File Compendium',
}
_DAOMU_BIJI_MEMBERS = {
    norm("The Grave Robbers' Chronicles Final Version"): 'Série principal',
    norm('Daomu Biji'): 'Série principal',
    norm("The Grave Robbers' Chronicles Restart Final Version"): 'Continuação',
    norm("The Grave Robbers' Chronicles Post Restart Sequels Final Version"): 'Continuação',
    norm("The Grave Robbers' Chronicles The Mystic Nine Final Version Updated"): 'Prelúdio',
    norm('The Mystic Nine'): 'Prelúdio',
    norm("The Grave Robbers' Chronicles The Southern Archives Final Version 2"): 'História paralela',
    norm("The Grave Robbers' Chronicles A Thousand Faces Final Version"): 'História paralela',
    norm("The Grave Robbers' Chronicles Volume New Years Specials and Extras Final Version"): 'Especiais',
    norm("The Grave Robbers' Chronicles Notes in Rain Village Final Version"): 'História paralela',
    norm("The Grave Robbers' Chronicles Wu Xie's Private Notes Final Version"): 'História paralela',
    norm('Moving Forward Through The Flowery Night The End Comes Without A Sound Final Version'): 'Continuação / extra',
    norm('The Mystic Nine Extras'): 'Prelúdio / extra',
}

_EXPLICIT_PRESENTATION_GROUPS = {
    "The Scum Villain's Self-Saving System": ('obra_00006','obra_00066','obra_00067'),
    'Case File Compendium': ('obra_00019','obra_00020','obra_00191','obra_00206','obra_00290','obra_02537'),
    'First-Class Lawyer': ('obra_00129','obra_00153'),
    'To Rule in a Turbulent World': ('obra_00021','obra_00044','obra_00944','obra_01186','obra_02621'),
    'No Moral': ('obra_00004','obra_00005','obra_00041'),
    'Tianbao Fuyao Lu': ('obra_00043','obra_00065'),
    'Love Sea': ('obra_00068','obra_00069','obra_00070','obra_00071','obra_00072','obra_00073'),
    'The Villain Has Something to Say': ('obra_00107','obra_00108'),
    "Love for Love's Sake": ('obra_00111','obra_00112'),
    "Trash of the Count's Family": ('obra_00103','obra_00104','obra_00114','obra_00759','obra_00946','obra_02567','obra_02519'),
    'UnPrison': ('obra_01318','obra_01319'),
    'Raven of the Inner Palace': ('obra_00102','obra_00124'),
    'The Case Files of Jeweler Richard': ('obra_00132','obra_00133','obra_02495','obra_02736'),
    'I Can Do It': ('obra_00173','obra_00174','obra_02024'),
    'The Perfect Destiny': ('obra_00078','obra_00159'),
    'KinnPorsche': ('obra_00079','obra_00080'),
    "The Legendary Master's Wife": ('obra_00083','obra_00084','obra_00085','obra_00086','obra_00087'),
    "The Beauty's Blade": ('obra_00937','obra_01680'),
    'Guardian: Zhen Hun': ('obra_00081','obra_00210','obra_00625','obra_00894'),
    'Copper Coins: Tong Qian Kan Shi': ('obra_00964','obra_02016'),
    'Little Mushroom': ('obra_00127','obra_00128','obra_01979'),
    'Semantic Error': ('obra_01320','obra_02574'),
    'Thousand Autumns: Qian Qiu': ('obra_01689','obra_00030','obra_00205'),
    'Circle of Inevitability': ('obra_01359','obra_02522'),
    'Error: Metamorphosis': ('obra_02470','obra_02749','obra_02772'),
    'Even If Everyone Hates You': ('obra_02259','obra_02823'),
    'Evening Stars of Southern Tibet': ('obra_02807','obra_02877'),
    'Tattoo': ('obra_00969','obra_02648'),
    'The Blind Concubine': ('obra_00049','obra_00877','obra_01124'),
    'The Abandoned Son Runs Rampant': ('obra_01149','obra_02734'),
    'The Sword Named No Way Out': ('obra_00629','obra_02982'),
    'The Trashy PD Has To Survive as an Idol': ('obra_02975','obra_02976'),
    'This Venerable One Really Didn’t Abandon My Familiar': ('obra_02719','obra_02721'),
    'Tsuki ga Michibiku Isekai Douchuu': ('obra_02753','obra_02754','obra_02755','obra_02756','obra_02757','obra_02758','obra_02759','obra_02760','obra_02761','obra_02762','obra_02763','obra_02764','obra_02765','obra_02766','obra_02767','obra_02768','obra_02769','obra_02770','obra_02771'),
    'There’s Something Wrong with the Chief: Du Zhu You Bing': ('obra_02842','obra_01069'),
    'Waiting For You Online': ('obra_00703','obra_02726'),
    'When Two Alphas Meet, One’s an Omega': ('obra_01443','obra_02920','obra_02814'),
    'Turning': ('obra_02102','obra_00547','obra_01491','obra_01695','obra_00438','obra_00953'),
    "The Hunter's Gonna Lay Low": ('obra_00123','obra_01352','obra_02382','obra_02679','obra_02779','obra_00267'),
    'The Husky and His White Cat Shizun': ('obra_00645','obra_00777','obra_00776','obra_01066','obra_02477'),
    'The Return of Cambrian Period': ('obra_00358','obra_02593'),
    'The S-Classes That I Raised': ('obra_00472','obra_00001','obra_02572'),
    'The Sickly Beauty Substitute Called It Quits': ('obra_02513','obra_02514','obra_02515'),
    'The Song of Achilles': ('obra_00493','obra_00558'),
    "The White Cat's Divine Scratching Post": ('obra_02829','obra_01581','obra_02315'),
    'Thriller Trainee': ('obra_00197','obra_02583'),
    'Tryst Six Venom': ('obra_00630','obra_00634'),
    'Welcome to the Nightmare Live': ('obra_01411','obra_02808'),
    'Tharntype': ('obra_00056','obra_00057'),
    "The Other World's Books Depend on the Bean Counter": ('obra_00012','obra_00013'),
    'Alabaster Penitentiary': ('obra_00096','obra_00097','obra_00098','obra_00099'),
    'Before the Coffee Gets Cold series': ('obra_00031','obra_00032'),
    '7 Minutes in Heaven': ('obra_03009','obra_02827'),
    'Application For Divorce': ('obra_00360','obra_02643'),
    'Children of the Holy Emperor': ('obra_00014','obra_00015'),
    'Pit Babe': ('obra_00464','obra_00773','obra_02624'),
    'The Last Gentleman (终末的绅士)': ('obra_00116',),
    'Under the Oak Tree': ('obra_00180','obra_00760','obra_00761','obra_00762',
                           'obra_00763','obra_00764','obra_00765','obra_00766',
                           'obra_00768','obra_00770','obra_00772','obra_01064',
                           'obra_01913','obra_02532','obra_02915'),
    'Artemis Fowl: The Arctic Incident': ('obra_00721',),
    'Artemis Fowl: The Opal Deception': ('obra_00726',),
    'Artemis Fowl: The Lost Colony': ('obra_00725',),
    '太子千秋万载': ('obra_01722',),
    '蝙蝠 (Bat)': ('obra_00705',),
    'Desire (垂涎)': ('obra_00842','obra_00898','obra_02641'),
    'Triage': ('obra_00513',),
    'Dear Benjamin': ('obra_00381','obra_00810','obra_00811'),
    'A Letter from Keanu Reeves': ('obra_01059','obra_02343','obra_02651','obra_02912','obra_02640'),
    'A Round Trip to Love': ('obra_01670','obra_01672','obra_01673'),
    'After Becoming a Cannon Fodder, I Bent the Villainous CEO': ('obra_02372','obra_03010'),
    'After I Turned From O to A I Became the National Male God': ('obra_00325',),
    'After Being Forced to Marry the Evil Star General': ('obra_02511','obra_02979'),
    'After Being Forced to Marry, I Was Pampered to Heaven': ('obra_03013',),
    'After I Got Married, Those Who Betrayed Me Were Reborn': ('obra_00359','obra_01195'),
    'After Killing My Way Through the Instance, I Raised the Evil God Within the Rules': ('obra_01244','obra_01302'),
    'After the Disabled God of War Became My Concubine': ('obra_02503','obra_02914'),
    'Transmigrating into the Prince Regent’s Beloved Runaway Wife': ('obra_00272','obra_00275'),
}

def presentation_title_key(row):
    title=str(row.get('titulo') or '').strip()
    generic=not title or re.fullmatch(r'[a-f0-9]{24,64}',title,re.I) or title.casefold() in {
        'book title','unknown','untitled','ebook','1 370582186'
    } or re.fullmatch(r'\d{1,5}\s+\d{6,}',title)
    if generic:
        title=next((str(name) for name in row.get('arquivos',[]) if name),title)
    title=re.sub(r'(?i)\.epub$','',title)
    title=re.sub(r'^\d+[_\s-]+','',title)
    title=re.sub(r'(?i)https?://\S+|t\.me/\S+|vk\.com/\S+',' ',title)
    title=re.sub(r'(?i)@[\w.-]+',' ',title)
    title=re.sub(r'(?i)[._\s-]+(?:z[._\s-]?library|oceanofpdf|chrysanthemum[._\s-]?garden|mtl|ftl|htl)\b.*$',' ',title)
    title=re.sub(r'(?i)\((?:z[- ]?lib(?:rary)?|oceanofpdf|mtl|ftl|htl|eng|raw|complete|completed|incomplete|digital|unofficial)[^)]*\)',' ',title)
    title=re.sub(r'(?i)\[(?:eng|mtl|ftl|htl|complete|completed|revised edition|main story end)[^\]]*\]',' ',title)
    volume=_PRESENTATION_VOLUME.search(title)
    if volume:
        title=title[:volume.start()]
    title=_PRESENTATION_CHAPTER_RANGE.sub(' ',title)
    title=re.sub(r'(?i)\b(?:sidestory|side story|epilogue|mini extras?|extras?|specials?|anthology|final version|updated|revised edition|raw novel|english edition|incomplete|completed|complete|mtl|ftl|htl|full)\b',' ',title)
    title=re.sub(r'(?i)\b(?:english|eng)\b',' ',title)
    title=re.sub(r'(?i)(?:^|[._\s])(?:en|pt|es|fr|ru|kr|cn|jp)\s*$',' ',title)
    title=re.sub(r"['’]s\b",'s',title)
    has_latin=any('LATIN' in unicodedata.name(char,'') for char in title if char.isalpha())
    if has_latin:
        title=''.join(char if not char.isalpha() or 'LATIN' in unicodedata.name(char,'') else ' ' for char in title)
    normalized=unicodedata.normalize('NFKD',title).casefold()
    normalized=''.join(char for char in normalized if not unicodedata.combining(char))
    normalized=''.join(char if char.isalnum() or char.isspace() else ' ' for char in normalized)
    normalized=' '.join(normalized.split())
    for alias,canonical in _PRESENTATION_ALIASES.items():
        alias_key=' '.join(unicodedata.normalize('NFKD',alias).casefold().split())
        if normalized==alias_key or normalized.startswith(alias_key+' '):
            return ' '.join(unicodedata.normalize('NFKD',canonical).casefold().split()),canonical
    return normalized,title.strip(' _-.,'),

def presentation_authors(row):
    """Return normalized author tokens used to keep homonymous works apart."""
    values=list(row.get('autores') or [])
    review=row.get('verificacao_obra') or {}
    if review.get('autor'):
        values.append(review['autor'])
    result=set()
    for value in values:
        # Parenthetical native spellings are aliases; split true co-authors.
        text=re.sub(r'\([^()]*\)', ' ', str(value))
        for part in re.split(r'(?i)\s+and\s+|\s*[;/&]\s*|\s*,\s*(?!\s)',text):
            key=norm(part)
            if key:result.add(key)
    return result

def presentation_authors_compatible(rows):
    author_sets=[presentation_authors(row) for row in rows]
    nonempty=[authors for authors in author_sets if authors]
    if len(nonempty)<2:return True
    # Require a shared author when both records name one. Explicit groups above
    # remain available for known pen names and translated author-name order.
    return all(bool(left & right) for i,left in enumerate(nonempty) for right in nonempty[i+1:])

def presentation_obras(payload):
    """Group only unambiguous explicit-volume rows for the Obras HTML view."""
    result=dict(payload)
    originals=[dict(row) for row in payload.get('obras',[])]
    candidates=defaultdict(list)
    for index,row in enumerate(originals):
        titles=[str(row.get('titulo') or '').strip(),*(row.get('titulos_alternativos') or [])]
        found=[]
        for title in dict.fromkeys(titles):
            marker=_PRESENTATION_VOLUME.search(title)
            if not marker:continue
            base=title[:marker.start()].strip(' ,:;_-')
            key=norm(base)
            if len(key)>=4:found.append((key,base,int(marker.group(1)),title))
        bases={entry[0] for entry in found}
        # A row already listing several volumes or aliases for different bases is ambiguous here.
        if len(bases)!=1 or len({entry[2] for entry in found})!=1:continue
        key,base,number,full_title=found[0]
        candidates[key].append((index,base,number,full_title))
    merges={}
    for key,entries in candidates.items():
        numbers=[entry[2] for entry in entries]
        if len(entries)<2:
            continue
        if len(set(numbers))!=len(numbers):
            for entry in entries:originals[entry[0]]['presentation_ambiguous']=True
            continue
        merges[entries[0][0]]=entries
    consumed=set();rows=[]
    for index,row in enumerate(originals):
        if index in consumed:continue
        entries=merges.get(index)
        if not entries:
            rows.append(row);continue
        children=[dict(originals[entry[0]]) for entry in entries]
        for child,entry in zip(children,entries):
            child['titulo']=entry[3]
        consumed.update(entry[0] for entry in entries)
        row['titulo']=entries[0][1]
        row['itens_serie']=children
        row['series_display']=True
        row['autores']=list(dict.fromkeys(author for child in children for author in child.get('autores',[])))
        row['arquivos']=list(dict.fromkeys(name for child in children for name in child.get('arquivos',[])))
        row['quantidade']=sum(int(child.get('quantidade',len(child.get('arquivos',[])))) for child in children)
        row['titulos_alternativos']=list(dict.fromkeys(title for child in children for title in [child.get('titulo',''),*(child.get('titulos_alternativos') or [])] if title and title!=row['titulo']))
        rows.append(row)
    for row in rows:
        if row.get('itens_serie') or len(row.get('arquivos',[]))<2:
            continue
        details=[]
        for title in row.get('titulos_alternativos',[]):
            marker=_PRESENTATION_VOLUME.search(str(title))
            if not marker:continue
            base=title[:marker.start()].strip(' ,:;_-')
            details.append((norm(base),title,int(marker.group(1))))
        if (len(details)<2 or len({entry[0] for entry in details})!=1
                or len({entry[2] for entry in details})!=len(details)):
            continue
        volume_details=[]
        for _,title,number in details:
            files=[name for name in row['arquivos']
                   if (m:=_PRESENTATION_VOLUME.search(Path(name).stem)) and int(m.group(1))==number]
            if files:
                volume_details.append({'titulo':title,'autores':row.get('autores',[]),'arquivos':files})
        if len(volume_details)==len(details):
            row['itens_serie']=volume_details
    franchise_matches=[(index,_DAOMU_BIJI_MEMBERS.get(norm(row.get('titulo',''))))
                       for index,row in enumerate(rows)
                       if norm(row.get('titulo','')) in _DAOMU_BIJI_MEMBERS]
    if len(franchise_matches)>1:
        member_indexes={index for index,_ in franchise_matches}
        children=[]
        for index,category in franchise_matches:
            child=dict(rows[index])
            child['categoria']=category;children.append(child)
        first_index=franchise_matches[0][0]
        parent=dict(rows[first_index])
        parent.update({
            'titulo':'Daomu Biji','itens_serie':children,'series_display':True,
            'autores':list(dict.fromkeys(author for child in children for author in child.get('autores',[]))),
            'arquivos':list(dict.fromkeys(name for child in children for name in child.get('arquivos',[]))),
            'quantidade':sum(int(child.get('quantidade',len(child.get('arquivos',[])))) for child in children),
            'titulos_alternativos':list(dict.fromkeys(child.get('titulo','') for child in children if child.get('titulo'))),
            'franquia':'Daomu Biji',
        })
        rows=[row for index,row in enumerate(rows) if index not in member_indexes]
        rows.insert(first_index,parent)
    for title,members in _EXPLICIT_PRESENTATION_GROUPS.items():
        member_set=set(members)
        def includes_member(row):
            if row.get('chave') in member_set:return True
            return any(includes_member(child) for child in row.get('itens_serie',[]))
        indexes=[index for index,row in enumerate(rows) if includes_member(row)]
        if len(indexes)==1:
            def member_ids(row):
                return ({row['chave']} if row.get('chave') else set()).union(
                    *(member_ids(child) for child in row.get('itens_serie',[]))
                )
            if member_set.issubset(member_ids(rows[indexes[0]])):
                rows[indexes[0]]['titulo']=title
            continue
        if len(indexes)<2:continue
        children=[]
        for index in indexes:
            children.append(dict(rows[index]))
        first_index=indexes[0]
        parent=dict(rows[first_index])
        parent.update({
            'titulo':title,'itens_serie':children,'series_display':True,
            'autores':list(dict.fromkeys(author for child in children for author in child.get('autores',[]))),
            'arquivos':list(dict.fromkeys(name for child in children for name in child.get('arquivos',[]))),
            'quantidade':sum(int(child.get('quantidade',len(child.get('arquivos',[])))) for child in children),
            'titulos_alternativos':list(dict.fromkeys(child.get('titulo','') for child in children if child.get('titulo'))),
        })
        index_set=set(indexes)
        rows=[row for index,row in enumerate(rows) if index not in index_set]
        rows.insert(first_index,parent)
    normalized_rows=defaultdict(list)
    for index,row in enumerate(rows):
        if row.get('presentation_ambiguous'):
            continue
        key,display=presentation_title_key(row)
        if len(key)>=3:
            normalized_rows[key].append((index,display))
    normalized_merges={}
    for key,entries in normalized_rows.items():
        if len(entries)>1:
            candidates=[rows[index] for index,_ in entries]
            if presentation_authors_compatible(candidates):
                normalized_merges[entries[0][0]]=entries
    consumed=set();normalized_result=[]
    for index,row in enumerate(rows):
        if index in consumed:continue
        entries=normalized_merges.get(index)
        if not entries:
            normalized_result.append(row);continue
        member_indexes={entry[0] for entry in entries}
        children=[]
        for member_index,_ in entries:
            member=rows[member_index]
            children.append(dict(member))
        consumed.update(member_indexes)
        parent=dict(rows[index]);parent['titulo']=entries[0][1]
        parent['itens_serie']=children;parent['series_display']=True
        parent['autores']=list(dict.fromkeys(author for child in children for author in child.get('autores',[])))
        parent['arquivos']=list(dict.fromkeys(name for child in children for name in child.get('arquivos',[])))
        parent['quantidade']=sum(int(child.get('quantidade',len(child.get('arquivos',[])))) for child in children)
        parent['titulos_alternativos']=list(dict.fromkeys(child.get('titulo','') for child in children if child.get('titulo') and child.get('titulo')!=parent['titulo']))
        normalized_result.append(parent)
    rows=normalized_result
    for row in rows:row.pop('presentation_ambiguous',None)
    for title,members in _EXPLICIT_PRESENTATION_GROUPS.items():
        member_set=set(members)
        def member_ids(row):
            return ({row['chave']} if row.get('chave') else set()).union(
                *(member_ids(child) for child in row.get('itens_serie',[]))
            )
        matching=next((row for row in rows if member_set.issubset(member_ids(row))),None)
        if matching:matching['titulo']=title
    for row in rows:
        reviews=[]
        def collect_reviews(item):
            if item.get('verificacao_obra'):reviews.append(item['verificacao_obra'])
            for child in item.get('itens_serie',[]):collect_reviews(child)
        collect_reviews(row)
        covered={name for review in reviews for name in review.get('epubs_lidos',[])}
        accounted_for=covered|{
            name for review in reviews for name in review.get('epubs_nao_lidos',[])
        }
        fields=('autor','nacionalidade_obra','protagonistas')
        if reviews and set(row.get('arquivos',[]))<=accounted_for and all(
            review.get(field)==reviews[0].get(field) for review in reviews for field in fields
        ):
            merged=dict(reviews[0]);merged['epubs_lidos']=sorted(covered)
            merged['epubs_nao_lidos']=sorted(accounted_for-covered)
            review_dates=[str(review.get('verificado_em','')) for review in reviews
                          if review.get('verificado_em')]
            if review_dates:merged['verificado_em']=max(review_dates)
            merged['referencias']=list(dict.fromkeys(
                link for review in reviews for link in review.get('referencias',[])
            ))
            row['verificacao_obra']=merged
        else:
            row.pop('verificacao_obra',None)
    rows.sort(key=lambda row: ''.join(
        char for char in unicodedata.normalize('NFKD',str(row.get('titulo',''))).casefold()
        if char.isalnum() or char.isspace()
    ))
    result['obras']=rows
    return result

def duplicate_report_groups(path, works_by_key):
    """Read the supplied visual-duplicate report and enrich members from JSON."""
    if not path.exists():return []
    text=path.read_text(encoding='utf-8')
    section='Repetição exata de título'
    groups=[];group=None;member=None
    def finish_member():
        nonlocal member
        if member and member.get('chave'):
            work=works_by_key.get(member['chave'],{})
            review=work.get('verificacao_obra') or {}
            source=str(review.get('fonte_nacionalidade') or '').strip()
            member.update({
                'pais':review.get('nacionalidade_obra') or 'Pendente',
                'pais_identificado_em':identification_source(source) if source else ('Fonte não registrada' if review.get('nacionalidade_obra') else 'Pendente'),
                'referencias':review.get('referencias') or [],
            })
            group['membros'].append(member)
        member=None
    def finish_group():
        nonlocal group
        finish_member()
        if group and len(group['membros'])>1:
            group['id']=f"{group['tipo']}:{len(groups)+1}"
            groups.append(group)
        group=None
    for line in text.splitlines():
        stripped=line.strip()
        if stripped.startswith('PARTE A -'):
            finish_group();section='Repetição exata de título';continue
        if stripped.startswith('PARTE B -'):
            finish_group();section='Candidato por volume ou subtítulo';continue
        header=re.match(r'^\[(\d+)\] TITULO-BASE: (.*?) \| LINHAS: (\d+) \|',stripped)
        if header:
            finish_group()
            group={'numero':int(header.group(1)),'titulo_base':header.group(2),
                   'tipo':section,'membros':[]}
            continue
        if group is None:continue
        key=re.match(r'^\(\d+\) CHAVE: (\S+)',stripped)
        if key:
            finish_member();member={'chave':key.group(1),'titulo':'','autor':'',
                                     'ids':[],'arquivos':[]}
            continue
        if member is None:continue
        for label,key_name in (('TITULO:','titulo'),('AUTOR(ES):','autor')):
            if stripped.startswith(label):member[key_name]=stripped[len(label):].strip();break
        else:
            if stripped.startswith('IDS:'):
                member['ids']=[value.strip() for value in stripped[4:].split(',') if value.strip()]
            elif stripped.startswith('- '):
                member['arquivos'].append(stripped[2:])
    finish_group()
    return groups

def load_author_aliases(root):
    path=root/'input'/'autores_de_para.json'
    if not path.exists():return {}
    raw=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw,dict):raise ValueError('Mapa de autores precisa ser um objeto JSON')
    aliases={}
    for source,target in raw.items():
        if not isinstance(source,str) or not isinstance(target,str):
            raise ValueError('Mapa de autores precisa conter apenas textos')
        key=unicodedata.normalize('NFC',source)
        if key in aliases and aliases[key]!=target:
            raise ValueError(f'Chave de autor conflitante após NFC: {source!r}')
        aliases[key]=target
    return aliases

def apply_author_aliases(records, aliases):
    for record in records:
        for field in ('autor','autor_obra'):
            value=record.get(field)
            if isinstance(value,str):
                key=unicodedata.normalize('NFC',value)
                record[field]=aliases.get(key,value)

def inject_html(original, payload, root):
    start='<!-- CHECK_EPUB_EXTRA_START -->';end='<!-- CHECK_EPUB_EXTRA_END -->'
    original=re.sub(re.escape(start)+r'.*?'+re.escape(end)+r'\s*','',original,flags=re.S)
    original=re.sub(r'<!-- CHECK_EPUB_NAV_START -->.*?<!-- CHECK_EPUB_NAV_END -->\s*','',original,flags=re.S)
    original=re.sub(r'<!-- CHECK_EPUB_SECTIONS_START -->.*?<!-- CHECK_EPUB_SECTIONS_END -->\s*','',original,flags=re.S)
    # Attach reviewed work metadata to matching EPUB rows in the main explorer.
    # Keep catalog language/country fields intact; nationality describes the
    # original work, and pending reviews still provide useful authors/protagonists.
    data_match=re.search(r'const DATA\s*=',original)
    if not data_match:raise ValueError('Dados DATA não encontrados no HTML; não alterado')
    data_start=data_match.end()
    report_data,data_end=json.JSONDecoder().raw_decode(original[data_start:])
    author_aliases=load_author_aliases(root)
    for work in payload.get('obras',[]):
        apply_cheonchusein_work(work)
        apply_zhichu_survivorship_work(work)
        apply_verified_title_corrections_work(work)
    works_by_key={str(work.get('chave','')):work for work in payload.get('obras',[])}
    duplicate_groups=duplicate_report_groups(
        root/'output'/'relatorio_completo_obras_duplicadas.txt',works_by_key)
    # Add the report-derived duplicate context to each EPUB row, keyed by message ID.
    duplicate_groups_by_id=defaultdict(list)
    for group in duplicate_groups:
        for member in group['membros']:
            for message_id in member.get('ids',[]):
                duplicate_groups_by_id[str(message_id)].append(group)
    for record in report_data.get('records',[]):
        apply_cheonchusein_record(record)
        apply_zhichu_survivorship_record(record)
        apply_verified_title_corrections(record)
        record['duplicatas_relatorio']=duplicate_groups_by_id.get(str(record.get('id','')),[])
    apply_author_aliases(report_data.get('records',[]),author_aliases)
    confirmed_files=set();confirmed_epub_ids=set();country_counts=Counter();country_epub_ids=defaultdict(set)
    confirmed_work_keys=set()
    display_payload=presentation_obras(payload)
    display_rows=display_payload.get('obras',[])
    display_payload['grupos_duplicatas_relatorio']=duplicate_groups
    for work in display_rows:
        review=work.get('verificacao_obra') or {}
        if review:work['verificadas_exibicao']=verification_display(review.get('verificado_em'))
    records_by_id={str(record.get('id','')):record for record in report_data.get('records',[])}
    for record in report_data.get('records',[]):
        record['localizada_em']='Pendente'
    def known_review(review):
        nationality=str((review or {}).get('nacionalidade_obra') or '').strip()
        normalized=nationality.casefold()
        return normalized not in {
            '', 'pendente', 'não identificada', 'nao identificada',
            'desconhecida', 'unknown', 'unknown nationality'
        } and not normalized.startswith(('não identificada', 'nao identificada'))
    # Reconcile Explorer rows against reviewed works, even when Telegram used
    # another message ID or filename. This keeps already identified works out
    # of Obras and prevents the same research from being repeated.
    def compact_author(value):
        return ''.join(char for char in unicodedata.normalize('NFKC',str(value or '')).casefold()
                       if char.isalnum())
    def comparable_title(value):
        value=str(value or '')
        value=re.sub(r'(?i)\b(?:vol(?:ume)?|v|book|part|chapter|ch)\s*\.?\s*\d+(?:\s*[-–]\s*\d+)?', ' ', value)
        value=re.sub(r'(?i)\b(?:nodrm|oceanofpdf(?:\.com)?|z[.]?library|1lib)\b', ' ', value)
        return norm(value)
    def title_match_score(left,right):
        a,b=comparable_title(left),comparable_title(right)
        if not a or not b:return 0
        if a==b:return 3
        shorter,longer=(a,b) if len(a)<=len(b) else (b,a)
        if len(shorter)>=12 and (longer.startswith(shorter+' ') or shorter.startswith(longer+' ')):return 2
        at,bt=set(a.split()),set(b.split())
        return 1 if len(shorter)>=16 and min(len(at),len(bt))>=2 and (at<=bt or bt<=at) else 0
    reviewed_by_title={}
    reviewed_by_prefix=defaultdict(set)
    reviewed_by_exact=defaultdict(set)
    for work in payload.get('obras',[]):
        review=work.get('verificacao_obra') or {}
        if not known_review(review):continue
        titles={comparable_title(work.get('titulo',''))}
        titles.update(comparable_title(title) for title in work.get('titulos_alternativos',[]) if title)
        titles.discard('')
        authors=[review.get('autor',''),*work.get('autores',[])]
        compact_authors=[compact_author(author) for author in authors if author]
        key=str(work.get('chave',''))
        reviewed_by_title[key]=(work,review,titles,compact_authors)
        for title in titles:
            reviewed_by_exact[title].add(key)
            words=title.split()
            for offset in range(max(1,len(words)-1)):
                reviewed_by_prefix[' '.join(words[offset:offset+2])].add(key)
    for record in report_data.get('records',[]):
        if record.get('obra_chave'):continue
        titles=[(record.get('catalogo',''),4),(record.get('titulo',''),4),
                (title_guess(record.get('nome','')),1)]
        normalized_titles=[(comparable_title(title),weight) for title,weight in titles if title]
        normalized_titles=[(title,weight) for title,weight in normalized_titles if title]
        possible_keys=set()
        for title,_ in normalized_titles:
            words=title.split()
            for offset in range(max(1,len(words)-1)):
                possible_keys.update(reviewed_by_prefix.get(' '.join(words[offset:offset+2]),()))
            possible_keys.update(reviewed_by_exact.get(title,()))
        record_text=compact_author(' '.join([record.get('autor',''),record.get('nome','')]))
        scored={}
        for key in possible_keys:
            work,review,known_titles,known_authors=reviewed_by_title[key]
            if record.get('autor') and not any(author in record_text for author in known_authors if len(author)>=6):continue
            score=max((title_match_score(title,known_title)*weight
                       for title,weight in normalized_titles for known_title in known_titles),default=0)
            if score:scored[key]=(score,work,review)
        if not scored:continue
        best=max(value[0] for value in scored.values())
        candidates={key:(work,review) for key,(score,work,review) in scored.items() if score==best}
        if len(candidates)>1:
            signatures={(country_name(review.get('nacionalidade_obra','')),
                         compact_author(review.get('autor') or ' / '.join(work.get('autores',[]))),
                         tuple(review.get('protagonistas') or []))
                        for work,review in candidates.values()}
            if len(signatures)!=1:continue
            work,review=min(candidates.values(),key=lambda pair:(len(norm(pair[0].get('titulo',''))),pair[0].get('chave','')))
        else:work,review=next(iter(candidates.values()))
        source=str(review.get('fonte_nacionalidade') or '').strip()
        nationality=country_name(review.get('nacionalidade_obra') or 'Pendente')
        record.update({
            'obra_verificada':work.get('titulo',''),
            'obra_chave':work.get('chave',''),
            'autor_obra':review.get('autor',''),
            'nacionalidade_obra':nationality,
            'protagonistas_obra':review.get('protagonistas',[]),
            'verificadas':verification_display(review.get('verificado_em')),
            'localizada_em':identification_source(source) if source else 'Fonte não registrada',
            'fonte_nacionalidade_obra':source,
            'referencia_obra':(review.get('referencias') or [''])[0],
        })
        reconciled_id=str(record.get('id','')).strip()
        if reconciled_id:
            confirmed_epub_ids.add(reconciled_id)
            country_epub_ids[nationality].add(reconciled_id)
    for work in payload.get('obras',[]):
        review=work.get('verificacao_obra') or {}
        if not review:continue
        is_confirmed=known_review(review)
        nationality=country_name(review.get('nacionalidade_obra') or 'Pendente')
        filenames=review.get('epubs_lidos') or work.get('arquivos',[])
        for filename in filenames:
            filename=str(filename)
            if is_confirmed:confirmed_files.add(filename)
            match=re.match(r'^(\d{1,9})[_\s-]',Path(filename).name)
            record_id=match.group(1) if match else ''
            record=records_by_id.get(record_id)
            if not record:continue
            nationality_source=str(review.get('fonte_nacionalidade') or '').strip()
            found_at=(identification_source(nationality_source) if is_confirmed and nationality_source
                      else ('Fonte não registrada' if is_confirmed else 'Pendente'))
            record.update({
                'obra_verificada':work.get('titulo',''),
                'obra_chave':work.get('chave',''),
                'autor_obra':review.get('autor',''),
                'nacionalidade_obra':nationality,
                'protagonistas_obra':review.get('protagonistas',[]),
                'verificadas':verification_display(review.get('verificado_em')),
                'localizada_em':found_at,
                'fonte_nacionalidade_obra':nationality_source,
                'referencia_obra':(review.get('referencias') or [''])[0],
            })
            if is_confirmed:
                confirmed_epub_ids.add(record_id)
                country_epub_ids[nationality].add(record_id)
    manually_verified_work_countries={}
    for record in report_data.get('records',[]):
        apply_cheonchusein_record(record)
        apply_zhichu_survivorship_record(record)
        if apply_verified_title_corrections(record):
            record_id=str(record.get('id','')).strip()
            if record_id:
                confirmed_epub_ids.add(record_id)
                country_epub_ids[country_name(record.get('nacionalidade_obra','Pendente'))].add(record_id)
            title_key=norm(record.get('obra_verificada') or record.get('titulo',''))
            if title_key:manually_verified_work_countries[title_key]=country_name(record.get('nacionalidade_obra','Pendente'))
    # Count reviewed works using the same presentation grouping as Obras.
    # The EPUB count below still counts every associated file in the Explorer.
    for work in display_rows:
        review=work.get('verificacao_obra') or {}
        if not known_review(review):continue
        nationality=country_name(review.get('nacionalidade_obra') or 'Pendente')
        country_counts[nationality]+=1
        confirmed_work_keys.add(str(work.get('chave') or work.get('titulo') or ''))
    displayed_work_titles={norm(work.get('titulo','')) for work in display_rows
                           if known_review(work.get('verificacao_obra') or {})}
    for title_key,nationality in manually_verified_work_countries.items():
        if title_key and title_key not in displayed_work_titles:
            country_counts[nationality]+=1
            confirmed_work_keys.add('manual:'+title_key)
            displayed_work_titles.add(title_key)
    report_data['obra_origins']={
        'work_count':len(confirmed_work_keys),
        'epub_count':len(confirmed_epub_ids),
        'countries':dict(country_counts),
        'country_details':{
            country:{'work_count':count,'epub_count':len(country_epub_ids.get(country,set()))}
            for country,count in country_counts.items()
        },
    }
    source=str(report_data.get('source') or '').strip()
    review_source='metadados de check_epub_obras.json'
    if review_source not in source:
        report_data['source']=' + '.join(part for part in (source,review_source) if part)
    report_data['generated']=datetime.now().strftime('%d/%m/%Y %H:%M')
    original=(original[:data_start]+safe_json(report_data)+
              original[data_start+data_end:])
    transferred=0
    for work in display_rows:
        files=set(map(str,work.get('arquivos',[])))
        work['nacionalidade_confirmada']=bool(files) and files<=confirmed_files
        transferred+=work['nacionalidade_confirmada']
    display_payload['obras_transferidas']=transferred
    display_payload['obras_revisadas_pendentes']=sum(
        bool(row.get('verificacao_obra')) and
        not known_review(row.get('verificacao_obra'))
        for row in payload.get('obras',[])
    )
    nav='''<button class="nav" id="nav-works" onclick="ceNavigate('works')" title="Obras"><span class="navicon">▤</span><span class="navlabel">Obras</span></button>'''
    if '</nav>' not in original or 'id="primaryTabs"' not in original or '</main>' not in original or '</body>' not in original:raise ValueError('Estrutura HTML inesperada; não alterada')
    original=original.replace('</nav>','<!-- CHECK_EPUB_NAV_START -->\n'+nav+'\n<!-- CHECK_EPUB_NAV_END -->\n</nav>',1)
    sections='''<!-- CHECK_EPUB_SECTIONS_START -->
<section id="works" class="hidden"><div class="eyebrow">Biblioteca / Obras</div><h1>Obras</h1><p class="sub">Obras ainda em revisão de nacionalidade, autoria ou personagens.</p><div class="panel"><style>.ce-author-control{position:relative;min-width:0}.ce-author-trigger{box-sizing:border-box;width:100%;min-height:44px;padding:10px 12px;border:1px solid #dfe5ee;border-radius:8px;background:#fff;color:#26364d;display:flex;align-items:center;justify-content:space-between;gap:8px;text-align:left;cursor:pointer}.ce-author-trigger:hover,.ce-author-trigger[aria-expanded="true"]{border-color:#3457a5}.ce-author-menu{position:absolute;z-index:30;top:calc(100% + 6px);right:0;width:min(420px,88vw);padding:8px;border:1px solid #dfe5ee;border-radius:8px;background:#fff;box-shadow:0 8px 24px #172b4d24}.ce-author-menu[hidden]{display:none}.ce-author-search{box-sizing:border-box;width:100%;padding:9px 10px;margin-bottom:7px;border:1px solid #dfe5ee;border-radius:6px}.ce-author-options{max-height:280px;overflow:auto}.ce-author-option{width:100%;display:flex;justify-content:space-between;gap:14px;padding:8px 9px;border:0;border-radius:5px;background:#fff;color:#26364d;text-align:left;cursor:pointer}.ce-author-option:hover,.ce-author-option[aria-selected="true"]{background:#f0f4fb}.ce-author-count{color:#77869b;white-space:nowrap}.ce-title-cell{display:flex;align-items:center;gap:8px}.ce-title-text{min-width:0}.ce-row-expander{display:grid;place-items:center;flex:0 0 22px;width:22px;height:22px;margin:0;padding:0;border:1px solid transparent;border-radius:5px;background:transparent;color:#718096;cursor:pointer}.ce-row-expander:hover,.ce-row-expander[aria-expanded="true"]{background:#f0f4fb;color:#334155;border-color:#e2e8f0}.ce-row-expander .ce-chevron{font-size:18px;line-height:1;transition:transform .15s ease}.ce-row-expander[aria-expanded="true"] .ce-chevron{transform:rotate(90deg)}.ce-data-row td{vertical-align:middle}.ce-detail-row[hidden]{display:none!important}.ce-detail-row:not([hidden]){display:table-row}.ce-detail-row>td{max-width:none!important;padding:0!important;background:#f8fafc!important;border-bottom:1px solid #e8edf3}.ce-expanded{box-sizing:border-box;width:100%;padding:14px 20px 16px 42px;background:#f8fafc;border-top:1px solid #e8edf3}.ce-expanded-heading{display:flex;align-items:center;gap:8px;margin:0 0 9px;color:#52627a;font-size:12px;font-weight:650}.ce-expanded-wrap{width:100%;overflow-x:auto}.ce-expanded-table{width:100%;min-width:760px;table-layout:fixed;font-size:12px;background:#fff;border:1px solid #e8edf3;border-radius:6px}.ce-expanded-table th{background:#f5f7fa;color:#77869b;font-size:11px;font-weight:600}.ce-expanded-table th:nth-child(1){width:27%}.ce-expanded-table th:nth-child(2){width:12%}.ce-expanded-table th:nth-child(3){width:10%}.ce-expanded-table th:nth-child(4){width:14%}.ce-expanded-table th:nth-child(5){width:17%}.ce-expanded-table th:nth-child(6){width:20%}.ce-expanded-table td,.ce-expanded-table th{max-width:none!important;padding:9px 11px;border-bottom:1px solid #e8edf3;vertical-align:top}.ce-expanded-table td:first-child{font-weight:550;color:#334155}.ce-expanded-table tbody tr:last-child td{border-bottom:0}.ce-expanded-table a{color:#3457a5}</style><style>.ce-main-table{width:100%;table-layout:fixed}.ce-main-table th:nth-child(1){width:30%}.ce-main-table th:nth-child(2){width:17%}.ce-main-table th:nth-child(3){width:12%}.ce-main-table th:nth-child(4){width:25%}.ce-main-table th:nth-child(5){width:10%}.ce-main-table th:nth-child(6){width:6%}.ce-data-row td{vertical-align:middle}.ce-detail-row[hidden]{display:none!important}.ce-detail-row:not([hidden]){display:table-row}.ce-detail-row>td{max-width:none!important;padding:0!important;background:#f8fafc!important;border-bottom:1px solid #e8edf3}.ce-expanded{box-sizing:border-box;width:100%;padding:14px 20px 16px 42px;background:#f8fafc;border-top:1px solid #e8edf3}.ce-expanded-heading{margin:0 0 8px;color:#52627a;font-size:12px;font-weight:650}.ce-expanded-wrap{display:block;width:100%;overflow-x:auto}.ce-expanded-table{display:table;box-sizing:border-box;width:100%;min-width:760px;table-layout:fixed;margin:0;background:#fff;border:1px solid #e8edf3;border-radius:6px;font-size:12px}.ce-expanded-table th{background:#f5f7fa;color:#77869b;font-size:11px;font-weight:600}.ce-expanded-table th:nth-child(1){width:27%}.ce-expanded-table th:nth-child(2){width:12%}.ce-expanded-table th:nth-child(3){width:10%}.ce-expanded-table th:nth-child(4){width:14%}.ce-expanded-table th:nth-child(5){width:17%}.ce-expanded-table th:nth-child(6){width:20%}.ce-expanded-table td,.ce-expanded-table th{max-width:none!important;padding:9px 11px;border-bottom:1px solid #e8edf3;vertical-align:top}.ce-expanded-table tbody tr:last-child td{border-bottom:0}.ce-expanded-table a{color:#3457a5}</style><style>.ce-detail-row[hidden]{display:none!important}.ce-detail-row:not([hidden]){display:table-row}.ce-detail-row>td{max-width:none!important;padding:0!important;background:#f8fafc!important;border-bottom:1px solid #e8edf3}.ce-expanded{box-sizing:border-box;width:100%;padding:14px 20px 16px 42px;background:#f8fafc;border-top:1px solid #e8edf3}.ce-expanded-heading{margin:0 0 8px;color:#52627a;font-size:12px;font-weight:650}.ce-expanded-wrap{display:block;width:100%;overflow-x:auto}.ce-expanded-table{display:table;box-sizing:border-box;width:100%;min-width:760px;table-layout:fixed;margin:0;background:#fff;border:1px solid #e8edf3;border-radius:6px;font-size:12px}.ce-expanded-table th{background:#f8fafc;color:#718096;font-size:11px;font-weight:600}.ce-expanded-table td,.ce-expanded-table th{max-width:none!important;padding:9px 11px;border-bottom:1px solid #e8edf3;vertical-align:top}.ce-expanded-table tbody tr:last-child td{border-bottom:0}.ce-expanded-table a{color:#3457a5}</style><div style="display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:10px;margin-bottom:18px"><input id="ce-search" placeholder="Buscar título, autor, protagonista ou arquivo" oninput="cePage=0;ceRender()" style="box-sizing:border-box;width:100%;min-width:0;padding:11px 12px;border:1px solid #dfe5ee;border-radius:8px;background:#fff;color:#26364d"><div class="ce-author-control" id="ce-author-filter"><button type="button" id="ce-author-button" class="ce-author-trigger" aria-haspopup="listbox" aria-expanded="false" onclick="ceToggleAuthorMenu()"><span id="ce-author-label">Todos os autores</span><span aria-hidden="true">⌄</span></button><div id="ce-author-menu" class="ce-author-menu" hidden><input id="ce-author-search" class="ce-author-search" placeholder="Buscar autor" aria-label="Buscar autor" oninput="ceRenderAuthorOptions()"><div id="ce-author-options" class="ce-author-options" role="listbox" aria-label="Autores"></div></div></div></div><div id="ce-works"></div></div></section>
<section id="pending" class="hidden"><div class="eyebrow">Biblioteca / Varredura local</div><h1>Baixadas não identificadas</h1><p class="sub">Obras baixadas ainda sem identificação confirmada, sem repetir cópias idênticas.</p><div class="panel" id="ce-pending"></div></section>
<section id="problems" class="hidden"><div class="eyebrow">Biblioteca / Pendências</div><h1>Problemas sem solução</h1><p class="sub">Somente falhas comprovadas sem outra cópia correspondente; situações não verificáveis permanecem separadas.</p><div class="panel" id="ce-problems"></div></section>
<section id="duplicates" class="hidden"><div class="eyebrow">Biblioteca / Auditoria</div><h1>Duplicatas</h1><p class="sub">Cópias idênticas e agrupamentos com evidência; títulos iguais sem autor não são mesclados automaticamente.</p><div class="panel" id="ce-duplicates"></div></section>
<!-- CHECK_EPUB_SECTIONS_END -->'''
    sections=sections.replace('<div class="eyebrow">Biblioteca / Obras</div><h1>Obras</h1><p class="sub">Obras ainda em revisão de nacionalidade, autoria ou personagens.</p>','')
    sections=sections.replace('<!-- CHECK_EPUB_SECTIONS_END -->','''<style>
#works .ce-data-row td{vertical-align:middle}
#works .ce-row-expander{border-color:#e8edf3;background:#fff}
#works .ce-row-expander:hover,#works .ce-row-expander[aria-expanded="true"]{border-color:#cbd5e1;background:#f0f4fb}
#works .ce-detail-row[hidden]{display:none!important}
#works .ce-detail-row:not([hidden]){display:table-row}
#works .ce-detail-row>td{display:table-cell!important;width:auto!important;max-width:none!important;padding:0!important;background:#f8fafc!important;border-bottom:1px solid #e8edf3}
#works .ce-expanded{box-sizing:border-box;display:block;width:100%;padding:14px 18px 16px 42px;background:#f8fafc;border-top:1px solid #e8edf3}
#works .ce-expanded-heading{margin:0 0 8px;color:#52627a;font-size:12px;font-weight:650}
#works .ce-expanded-wrap{display:block;width:100%;overflow-x:auto}
#works .ce-expanded-table{display:table;box-sizing:border-box;width:100%;min-width:640px;margin:0;border:1px solid #e8edf3;border-radius:6px;border-collapse:collapse;table-layout:fixed;background:#fff;font-size:12px}
#works .ce-expanded-table th{background:#f8fafc;color:#718096;font-size:11px;font-weight:600}
#works .ce-expanded-table td,#works .ce-expanded-table th{max-width:none!important;padding:8px 10px;border-bottom:1px solid #e8edf3;vertical-align:top}
#works .ce-expanded-table{min-width:900px}
#works .ce-expanded-table th:nth-child(1){width:18%}#works .ce-expanded-table th:nth-child(2){width:22%}#works .ce-expanded-table th:nth-child(3){width:12%}#works .ce-expanded-table th:nth-child(4){width:8%}#works .ce-expanded-table th:nth-child(5){width:11%}#works .ce-expanded-table th:nth-child(6){width:14%}#works .ce-expanded-table th:nth-child(7){width:15%}
#works .ce-expanded-table tbody tr:last-child td{border-bottom:0}
#works .ce-expanded-table a{color:#3457a5}
</style><!-- CHECK_EPUB_SECTIONS_END -->''')
    original=original.replace('</main>',sections+'\n</main>',1)
    js='''<script>
const CE_DATA=__CE_PAYLOAD__;
const ceEsc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function ceCatalogPendingGroups(){const localIds=new Set();function collectIds(work){(work.ids||[]).forEach(id=>localIds.add(String(id)));(work.arquivos||[]).forEach(file=>{const match=String(file).match(/^(\d{1,9})[_\s-]/);if(match)localIds.add(match[1]);});(work.itens_serie||[]).forEach(collectIds)}CE_DATA.obras.forEach(collectIds);const pendingCountries=new Set(['Pendente','Não identificada','Conflito']);return novelGroups.filter(group=>pendingCountries.has(group.country)&&!group.records.some(record=>{const match=String(record.nome||'').match(/^(\d{1,9})[_\s-]/);return localIds.has(String(record.id||match?.[1]||''));})).map((group,index)=>{const author=group.authors.join(' / '),protagonists=group.protagonistList||[],observations=group.records.map(record=>[record.nacionalidade_obra,record.observacao_obra,record.criterio_nacionalidade].filter(Boolean).join(' ')).filter(Boolean).join(' | ');const children=group.records.map(record=>{const match=String(record.nome||'').match(/^(\d{1,9})[_\s-]/),id=String(record.id||match?.[1]||'');return {chave:'catalog:'+group.key+':'+id,titulo:group.title,ids:id?[id]:[],arquivos:record.nome?[record.nome]:[],autores:group.authors,quantidade:1,verificacao_obra:{autor:author,nacionalidade_obra:group.country,protagonistas:protagonists,observacao:record.nacionalidade_obra||'',fonte_nacionalidade:record.fonte_nacionalidade_obra||'',referencias:record.referencia_obra?[record.referencia_obra]:[]}}});return {chave:'catalog_pending:'+index+':'+group.key,titulo:group.title,titulos_alternativos:[],autores:group.authors,arquivos:group.records.map(record=>record.nome).filter(Boolean),ids:group.records.map(record=>String(record.id||'')).filter(Boolean),quantidade:group.records.length,itens_serie:children,nacionalidade_confirmada:false,nacionalidade_obra:group.country,protagonistas_obra:protagonists,catalog_evidence:observations,verificadas_exibicao:group.verified||'Pendente'};});}
const CE_CATALOG_PENDING=ceCatalogPendingGroups();
function ceVerifiedLabel(value){const m=String(value||'').match(/^(\\d{4})-(\\d{2})-(\\d{2})(?:[T ](\\d{2}):(\\d{2}):(\\d{2}))?/);return m?m[3]+'/'+m[2]+'/'+m[1]+(m[4]?' '+m[4]+':'+m[5]+':'+m[6]:''):(value||'Pendente');}
const ceViews=['overview','novels','explorer','works','pending','problems','duplicates'];
function ceNavigate(v){if(!ceViews.includes(v))v='overview';const section=v==='novels'?'overview':v;for(const n of ['overview','explorer','works','pending','problems','duplicates'])document.getElementById(n)?.classList.toggle('hidden',n!==section);document.getElementById('overviewPanel')?.classList.toggle('hidden',v!=='overview');document.getElementById('novelsPanel')?.classList.toggle('hidden',v!=='novels');ceViews.forEach(n=>document.getElementById('nav-'+n)?.classList.toggle('active',n===v));location.hash=v;}
const ceOriginalNavigate=navigate;
navigate=ceNavigate;
let cePage=0;const cePageSize=50;
function ceDetails(g){if(g.itens_serie?.length)return g.itens_serie.map(v=>'<div style="padding:8px 0;border-bottom:1px solid #eee"><strong>'+ceEsc(v.titulo)+'</strong>'+(v.categoria?'<div>Categoria: '+ceEsc(v.categoria)+'</div>':'')+'<div>Autor: '+ceEsc(v.autores.join(', ')||'Não informado')+'</div>'+v.arquivos.map(f=>'<div>Arquivo: '+ceEsc(f)+'</div>').join('')+'</div>').join('');return g.arquivos.map(f=>'<div style="padding:5px 0">'+ceEsc(f)+'</div>').join('');}
function ceWorkAuthor(g){const v=g.verificacao_obra||{};return String(v.autor||(g.autores||[]).join(', ')||'Não informado');}
function ceIsFanfic(g){const v=g.verificacao_obra||{};const evidence=[g.titulo,...(g.titulos_alternativos||[]),g.catalog_evidence||'',v.nacionalidade_obra||'',v.autor||'',v.criterio_nacionalidade||'',v.observacao||'',JSON.stringify(v.pesquisa_direcionada||{}),JSON.stringify(v.pesquisa_novel_updates||{})].join(' ').normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'').toLocaleLowerCase('pt-BR');return /\\b(fanfic|fanfiction|fan fiction|fanwork|fan work)\\b/.test(evidence);}
function ceAuthorNorm(value){return String(value||'').normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'').toLocaleLowerCase('pt-BR').replace(/[^\\p{L}\\p{N}]+/gu,' ').trim().replace(/\\s+/g,' ');}
function ceWorkAuthorAliases(g){const raw=ceWorkAuthor(g);const aliases=[raw,raw.replace(/\\([^()]*\\)/g,' ').replace(/\\s+/g,' ').trim(),...[...raw.matchAll(/\\(([^()]*)\\)/g)].map(m=>m[1])];return [...new Set(aliases.map(ceAuthorNorm).filter(Boolean))];}
const ceAuthorParents=new Map();
function ceAuthorFind(key){if(!ceAuthorParents.has(key))ceAuthorParents.set(key,key);let parent=ceAuthorParents.get(key);if(parent!==key){parent=ceAuthorFind(parent);ceAuthorParents.set(key,parent);}return parent;}
function ceBuildAuthorIndex(){const works=[...CE_DATA.obras,...CE_CATALOG_PENDING].filter(g=>!g.nacionalidade_confirmada&&!ceIsFanfic(g));for(const g of works){const aliases=ceWorkAuthorAliases(g);for(const alias of aliases)ceAuthorFind(alias);for(let i=1;i<aliases.length;i++){const a=ceAuthorFind(aliases[0]),b=ceAuthorFind(aliases[i]);if(a!==b){if(a<b)ceAuthorParents.set(b,a);else ceAuthorParents.set(a,b);}}}const labels=new Map(),counts=new Map(),aliasesByGroup=new Map();for(const g of works){const group=ceAuthorFind(ceWorkAuthorAliases(g)[0]),label=ceWorkAuthor(g);counts.set(group,(counts.get(group)||0)+1);if(!labels.has(group))labels.set(group,new Map());labels.get(group).set(label,(labels.get(group).get(label)||0)+1);if(!aliasesByGroup.has(group))aliasesByGroup.set(group,new Set());ceWorkAuthorAliases(g).forEach(alias=>aliasesByGroup.get(group).add(alias));}const result=new Map();for(const [group,count] of counts){const label=[...labels.get(group)].sort((a,b)=>b[1]-a[1]||a[0].length-b[0].length||a[0].localeCompare(b[0],'pt-BR'))[0][0];result.set(group,{label,count,aliases:[...aliasesByGroup.get(group)]});}return result;}
const ceAuthorIndex=ceBuildAuthorIndex();let ceSelectedAuthor='';let ceAuthorCounts=[];let ceFanficCount=0;
function ceToggleAuthorMenu(){const menu=document.getElementById('ce-author-menu');const button=document.getElementById('ce-author-button');menu.hidden=!menu.hidden;button.setAttribute('aria-expanded',String(!menu.hidden));if(!menu.hidden){ceRenderAuthorOptions();document.getElementById('ce-author-search').focus();}}
function ceCloseAuthorMenu(){const menu=document.getElementById('ce-author-menu');if(!menu)return;menu.hidden=true;document.getElementById('ce-author-button')?.setAttribute('aria-expanded','false');}
function ceSelectAuthor(author){ceSelectedAuthor=author;cePage=0;ceCloseAuthorMenu();ceRender();}
function ceRenderAuthorOptions(){const query=(document.getElementById('ce-author-search')?.value||'').trim().toLocaleLowerCase();const allCount=ceAuthorCounts.reduce((sum,item)=>sum+item[1].count,0);const options=[['','Todos os autores',allCount,''],...(ceFanficCount?[['__fanfic__','Fanfic',ceFanficCount,'']]:[]),...ceAuthorCounts.map(([key,info])=>[key,info.label,info.count,info.aliases.join(' ')])].filter((item,index)=>index===0||!query||(item[1]+' '+item[3]).toLocaleLowerCase().includes(query));document.getElementById('ce-author-options').innerHTML=options.map(([value,label,count])=>'<button type="button" class="ce-author-option" role="option" aria-selected="'+String(value===ceSelectedAuthor)+'" data-author="'+ceEsc(value)+'" title="'+(value==='__fanfic__'?'Histórias derivadas de obras, universos ou personagens existentes':'')+'" onclick="ceSelectAuthor(this.dataset.author)"><span>'+ceEsc(label)+'</span><span class="ce-author-count">'+count+'</span></button>').join('')||'<div class="muted" style="padding:9px">Nenhum autor encontrado.</div>';}
document.addEventListener('click',event=>{if(!event.target.closest('#ce-author-filter'))ceCloseAuthorMenu();});
document.addEventListener('keydown',event=>{if(event.key==='Escape')ceCloseAuthorMenu();});
function ceDuplicateGroupsFor(work){const keys=new Set();function collect(item){if(item?.chave)keys.add(String(item.chave));(item?.itens_serie||[]).forEach(collect);}collect(work);return (CE_DATA.grupos_duplicatas_relatorio||[]).filter(group=>group.membros.some(member=>keys.has(String(member.chave))));}
function ceSourceLabel(value){if(!value)return '';try{const host=new URL(value).hostname.replace(/^www\\./,'');const names={'novelupdates.com':'Novel Updates','jjwxc.net':'JJWXC','ridibooks.com':'RIDI Books','sevenseasentertainment.com':'Seven Seas','yenpress.com':'Yen Press','goodreads.com':'Goodreads','books.google.com':'Google Books','google.com':'Google Books','mebmarket.com':'MEB Market','fanqienovel.com':'Fanqie Novel','webnovel.com':'Webnovel','wattpad.com':'Wattpad','tunwalai.com':'Tunwalai','wtr-lab.com':'WTR-Lab','marinetl.xyz':'MarineTL'};return names[host]||host;}catch{return value;}}
function ceWorkLeaves(work){const children=work.itens_serie||[];return children.length?children.flatMap(ceWorkLeaves):[work];}
function ceExpandedReferenceLinks(urls){return (urls||[]).length?urls.map((url,index)=>'<a href="'+ceEsc(url)+'" target="_blank" rel="noopener noreferrer">'+((urls.length>1)?'Abrir '+(index+1):'Abrir')+'</a>').join(' · '):'—';}
function ceWorkDetailsMarkup(work,groups){const entries=ceWorkLeaves(work).map(item=>{const v=item.verificacao_obra||{};const ids=item.ids?.length?item.ids:(item.arquivos||[]).map(file=>String(file).match(/^(\d{1,9})[_\s-]/)?.[1]).filter(Boolean);const source=ceSourceLabel(v.fonte_nacionalidade);return {title:item.titulo||work.titulo,files:item.arquivos||[],key:item.chave||'—',ids:ids.join(', ')||'—',country:v.nacionalidade_obra||'Pendente',found:source||(v.nacionalidade_obra?'Fonte não registrada':'Pendente'),refs:v.referencias||[]};});const ownKeys=new Set(entries.map(item=>String(item.key)));(groups||[]).forEach(group=>(group.membros||[]).forEach(member=>{if(!ownKeys.has(String(member.chave)))entries.push({title:member.titulo||'Obra sem título',files:member.arquivos||[],key:member.chave||'—',ids:(member.ids||[]).join(', ')||'—',country:member.pais||'Pendente',found:member.pais_identificado_em||'Pendente',refs:member.referencias||[]});}));const rows=entries.map(item=>'<tr><td>'+ceEsc(item.title)+'</td><td>'+ceEsc(item.files.join(', ')||'—')+'</td><td>'+ceEsc(item.key)+'</td><td>'+ceEsc(item.ids)+'</td><td>'+ceEsc(item.country)+'</td><td>'+ceEsc(item.found)+'</td><td>'+ceExpandedReferenceLinks(item.refs)+'</td></tr>').join('');const heading=(groups||[]).length?((groups||[]).length+' grupo(s) de duplicatas relacionado(s)'):'Dados da obra';return '<div class="ce-expanded"><p class="ce-expanded-heading">'+ceEsc(heading)+'</p><div class="ce-expanded-wrap"><table class="ce-expanded-table"><thead><tr><th>Obra / registro relacionado</th><th>Arquivo EPUB</th><th>Chave</th><th>ID(s)</th><th>País de origem</th><th>País identificado em</th><th>Referência</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>';}
function ceToggleWorkDetails(button){const row=document.getElementById(button.getAttribute('aria-controls'));const expanded=button.getAttribute('aria-expanded')==='true';button.setAttribute('aria-expanded',String(!expanded));row.hidden=expanded;}
function ceTable(items,obrasMode=false,scope='table'){if(!items.length)return '<p class="muted">Nenhum registro disponível nesta categoria.</p>';
const detailsHeader=obrasMode?'':'<th>Detalhes</th>';
const reviewHeaders=obrasMode?'<th>País de origem</th><th>Protagonistas</th>':'';
const columns=obrasMode?6:4;
const body=items.map((g,index)=>{let v=g.verificacao_obra||{};let author=obrasMode&&v.autor?v.autor:(g.autores.join(', ')||'Não informado');if(!obrasMode)return '<tr><td><strong>'+ceEsc(g.titulo)+'</strong></td><td>'+ceEsc(author)+'</td><td>'+g.quantidade+'</td><td><details><summary style="cursor:pointer;color:#3457a5">Ver arquivos associados</summary><div style="padding:10px 0;max-width:550px">'+ceDetails(g)+'</div></details></td></tr>';const detailId=scope+'-details-'+index;return '<tr class="ce-data-row"><td><div class="ce-title-cell"><button type="button" class="ce-row-expander" aria-label="Expandir dados e possíveis duplicatas" title="Expandir dados e possíveis duplicatas" aria-expanded="false" aria-controls="'+detailId+'" onclick="ceToggleWorkDetails(this)"><span class="ce-chevron" aria-hidden="true">›</span></button><strong class="ce-title-text">'+ceEsc(g.titulo)+'</strong></div></td><td>'+ceEsc(author)+'</td><td>'+ceEsc(v.nacionalidade_obra||g.nacionalidade_obra||'Pendente')+'</td><td>'+ceEsc((v.protagonistas||g.protagonistas_obra||[]).join(' / ')||'Pendente')+'</td><td>'+ceEsc(g.verificadas_exibicao||ceVerifiedLabel(v.verificado_em))+'</td><td>'+g.quantidade+'</td></tr><tr id="'+detailId+'" class="ce-detail-row" hidden><td colspan="'+columns+'">'+ceWorkDetailsMarkup(g,ceDuplicateGroupsFor(g))+'</td></tr>';}).join('');
return '<div class="tablewrap"><table class="ce-main-table"><thead><tr><th>Obra</th><th>Autor</th>'+reviewHeaders+(obrasMode?'<th>Verificadas</th>':'')+'<th>Arquivos</th>'+detailsHeader+'</tr></thead><tbody>'+body+'</tbody></table></div>';
}
function ceVerificationTime(work){const value=work.verificacao_obra?.verificado_em||work.verificadas_exibicao||'';const timestamp=Date.parse(value);return Number.isFinite(timestamp)?timestamp:0;}
function ceSeriesFamily(work){if(ceIsFanfic(work))return '';const titles=[work.titulo,...(work.titulos_alternativos||[]),...(work.itens_serie||[]).map(item=>item.titulo)].filter(Boolean);const text=titles.join(' ').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');if(/\bfor a thousand autum(?:n)?s\b/.test(text))return '';const rules=[
  ['Grandmaster of Demonic Cultivation',/grandmaster of demonic cultivation|mo dao zu shi/],
  ['The Apothecary Diaries',/apothecary diaries/],['10 DANCE',/\\b10 dance\\b/],['Thousand Autumns',/thousand autumns|qian qiu/],
  ['Hate Me, but Let Me Stay',/hate me but let me stay/],['The Moon on a Rainy Night',/moon on a rainy night/],['The Summer You Were There',/summer you were there/],
  ['Joyful Reunion',/joyful reunion/],['Lullaby of the Dawn',/lullaby of the dawn/],['The Husky and His White Cat Shizun',/husky and his white cat shizun|erha he ta de bai mao/],
  ['Dinghai Fusheng Records',/dinghai fusheng records/],['Peerless',/\\bpeerless\\b/],['World’s End Blue Bird',/world.s end blue bird/],['No God in Eden',/no god in eden/],
  ['Remnants of Filth (Yuwu)',/remnants of filth|\\byuwu\\b/],['Run Away With Me, Girl',/run away with me girl/],['Run Wild (Sa Ye)',/run wild|\\bsa ye\\b/],
  ['Stars of Chaos (Sha Po Lang)',/stars of chaos|sha po lang/],['Silent Reading (Mo Du)',/silent reading|\\bmo du\\b/],['The Dangerous Convenience Store',/dangerous convenience store/],
  ['Three Hundred Years of Longing',/three hundred years of longing/],['Thrice Married to a Salted Fish',/thrice married to a salted fish/],['Ballad of Sword and Wine (Qiang Jin Jiu)',/ballad of sword and wine|qiang jin jiu/],
  ['Case File Compendium (Bing An Ben)',/case file compendium|bing an ben/],['Guardian (Zhen Hun)',/guardian zhen hun|\\bzhen hun\\b/],
  ['Legend of Exorcism (Tianbao Fuyao Lu)',/legend of exorcism|tianbao fuyao lu/],['Copper Coins (Tong Qian Kan Shi)',/copper coins|tong qian kan shi/],
  ['The Wife Comes First (Qi Wei Shang)',/wife comes first|qi wei shang/],['Twin Jades of Jiangdong',/twin jades of jiangdong/],['Villains Are Destined to Die',/villains are destined to die/],
  ['The Summer Hikaru Died',/summer hikaru died/],['You’ve Got Mail',/you.ve got mail|perils of pigeon post/],['Your Forma',/your forma|electronic investigator echika/],
  ['The Disabled Tyrant’s Beloved Pet Fish',/disabled tyrant.s beloved pet fish|canji baojun de zhangxin yu/],['Secrets of the Silent Witch',/secrets of the silent witch/],
  ['Lord of Mysteries',/lord of (?:the )?mysteries/],['Eiderdown',/\beiderdown\b/],['Golden Terrace',/golden terrace/],['Hell Is Dark with No Flowers',/hell is dark with no flowers/],
  ['Hidden Love',/\\bhidden love\\b/],['Interminable',/\\binterminable\\b/],['Look at Me',/look at me/],['Love Between Fairy and Devil',/love between fairy and devil/],
  ['Omniscient Reader’s Viewpoint',/omniscient readers? viewpoint/],['Panguan: The Twelfth Gate',/panguan|twelfth gate/],['The Only Sunflower I See Is You',/only sunflower i see is you/],
  ['The Villain’s White Halo',/villain.s white halo/],['At the World’s Mercy',/at the world.s mercy/],['Deadman Switch',/deadman switch/],
  ['Go For It, Nakamura!',/go for it(?: again)? nakamura/],['Earthian',/\\bearthian\\b/],['Megumi & Tsugumi',/megumi.*tsugumi/],['School Trip: Joined a Group I’m Not Close To',/school trip joined a group/],
  ['Strawberry Panic!',/strawberry panic/],['Rose & Renaissance',/rose renaissance/],['Trascendiendo la Semilla del Mal',/trascendiendo la semilla del mal/],
  ['The Scum Villain’s Self-Saving System',/scum villain.s self saving system|ren zha fanpai zijiu xitong|\bsvss\b/]
];for(const [label,pattern] of rules)if(pattern.test(text)){if(label==='The Scum Villain’s Self-Saving System'&&/bingjiu|fanfic|fanfiction/.test(text))return '';return label}return '';}
function ceGroupSeriesRows(items){const grouped=new Map();for(const item of items){const family=ceSeriesFamily(item);if(!family)continue;if(!grouped.has(family))grouped.set(family,[]);grouped.get(family).push(item)}const consumed=new Set(),result=[];for(const [family,members] of grouped){if(members.length<2)continue;members.forEach(item=>consumed.add(item));const children=members.flatMap(item=>item.itens_serie?.length?item.itens_serie:[item]);const unique=(values)=>[...new Set(values.filter(Boolean))];const authors=unique(members.flatMap(item=>[...(item.autores||[]),item.verificacao_obra?.autor||'']));const files=unique(members.flatMap(item=>item.arquivos||[]));const ids=unique(members.flatMap(item=>item.ids||[]));const countries=unique(members.map(item=>item.verificacao_obra?.nacionalidade_obra||item.nacionalidade_obra).filter(value=>value&&value!=='Pendente'&&!String(value).startsWith('Não identificada')));const protagonists=unique(members.flatMap(item=>item.verificacao_obra?.protagonistas||item.protagonistas_obra||[]));const parent={...members[0],chave:'serie:'+family,titulo:family,autores:authors,arquivos:files,ids,quantidade:members.reduce((n,item)=>n+Number(item.quantidade||item.arquivos?.length||item.ids?.length||1),0),titulos_alternativos:unique(members.flatMap(item=>[item.titulo,...(item.titulos_alternativos||[])]).filter(title=>title&&title!==family)),itens_serie:children,protagonistas_obra:protagonists,nacionalidade_obra:countries.length===1?countries[0]:'Pendente',nacionalidade_confirmada:false};delete parent.verificacao_obra;result.push(parent)}return [...items.filter(item=>!consumed.has(item)),...result].sort((a,b)=>ceVerificationTime(b)-ceVerificationTime(a)||a.titulo.localeCompare(b.titulo,'pt-BR',{sensitivity:'base'}));}
function ceRender(){let q=(document.getElementById('ce-search')?.value||'').trim().toLowerCase();let matching=[...CE_DATA.obras,...CE_CATALOG_PENDING].filter(g=>!g.nacionalidade_confirmada&&[g.titulo,...g.titulos_alternativos,...g.autores,...g.arquivos,...(g.verificacao_obra?.protagonistas||[]),g.verificacao_obra?.autor||'',g.verificacao_obra?.nacionalidade_obra||'',JSON.stringify(g.itens_serie||[])].join(' ').toLowerCase().includes(q)).sort((a,b)=>ceVerificationTime(b)-ceVerificationTime(a)||a.titulo.localeCompare(b.titulo,'pt-BR',{sensitivity:'base'}));let fanfics=matching.filter(ceIsFanfic),ordinary=matching.filter(g=>!ceIsFanfic(g));ceFanficCount=fanfics.length;let counts=new Map();ordinary.forEach(g=>{let author=ceAuthorFind(ceWorkAuthorAliases(g)[0]);counts.set(author,(counts.get(author)||0)+1)});ceAuthorCounts=[...counts].map(([key,count])=>[key,{...ceAuthorIndex.get(key),count}]).sort((a,b)=>a[1].label.localeCompare(b[1].label,'pt-BR',{sensitivity:'base'}));if(ceSelectedAuthor!=='__fanfic__'&&ceSelectedAuthor&&!counts.has(ceSelectedAuthor))ceSelectedAuthor='';if(ceSelectedAuthor==='__fanfic__'&&!ceFanficCount)ceSelectedAuthor='';let selectedInfo=ceAuthorIndex.get(ceSelectedAuthor);let label=ceSelectedAuthor==='__fanfic__'?'Fanfic ('+ceFanficCount+')':selectedInfo?selectedInfo.label+' ('+counts.get(ceSelectedAuthor)+')':'Todos os autores ('+ordinary.length+')';document.getElementById('ce-author-label').textContent=label;if(!document.getElementById('ce-author-menu').hidden)ceRenderAuthorOptions();let works=ceSelectedAuthor==='__fanfic__'?fanfics:ordinary.filter(g=>!ceSelectedAuthor||ceAuthorFind(ceWorkAuthorAliases(g)[0])===ceSelectedAuthor);
works=ceGroupSeriesRows(works);let pages=Math.max(1,Math.ceil(works.length/cePageSize));cePage=Math.min(cePage,pages-1);let shown=works.slice(cePage*cePageSize,(cePage+1)*cePageSize);
document.getElementById('ce-works').innerHTML='<p class="muted">'+works.length+' obras exibidas · '+CE_CATALOG_PENDING.length+' grupos pendentes do catálogo sem correspondência na varredura local · '+CE_DATA.obras_transferidas+' transferidas ao Explorador por nacionalidade confirmada · '+CE_DATA.obras_revisadas_pendentes+' revisadas aguardando confirmação · '+CE_DATA.total_arquivos+' EPUBs válidos.</p>'+ceTable(shown,true,'works')+'<div style="display:flex;justify-content:flex-end;align-items:center;gap:12px;margin-top:14px"><button type="button" onclick="ceMove(-1)" '+(cePage===0?'disabled':'')+'>Anterior</button><span class="muted">Página '+(cePage+1)+' de '+pages+'</span><button type="button" onclick="ceMove(1)" '+(cePage>=pages-1?'disabled':'')+'>Próximo</button></div>';
document.getElementById('ce-pending').innerHTML='<p class="muted">'+CE_DATA.pendentes.length+' agrupamentos pendentes. Identificação baseada apenas em evidências locais.</p>'+ceTable(CE_DATA.pendentes);
document.getElementById('ce-problems').innerHTML='<p class="muted">'+CE_DATA.problemas.length+' falhas sem alternativa comprovadas. '+CE_DATA.problemas_indeterminados+' casos não classificáveis por falta de histórico completo de tentativas.</p>'+ceTable(CE_DATA.problemas);
document.getElementById('ce-duplicates').innerHTML='<p class="muted">'+CE_DATA.duplicatas.length+' grupos com mais de um arquivo; '+CE_DATA.duplicatas_identificadas_catalogo.length+' grupos de título+autor repetidos entre os identificados no catálogo.</p>'+ceTable(CE_DATA.duplicatas);}
function ceMove(delta){cePage+=delta;ceRender();}
ceRender();ceNavigate(ceViews.includes(location.hash.slice(1))?location.hash.slice(1):'overview');
</script>'''.replace('__CE_PAYLOAD__',safe_json(display_payload))
    return original.replace('</body>',start+'\n'+js+'\n'+end+'\n</body>',1)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--projeto',type=Path,default=Path.cwd())
    ap.add_argument('--epubs',type=Path,help='Pasta de EPUBs baixados (varredura recursiva)')
    ap.add_argument('--somente-html',action='store_true',help='Reusar varredura já salva')
    args=ap.parse_args();root=args.projeto.expanduser().resolve()
    if not (root/'output').is_dir():ap.error('Pasta output/ não encontrada no projeto')
    out=root/'output';scanfile=out/'check_epub_varredura.json'
    csvpath=out/'telegram_midias_apenas_epub_origens_v3_ptbr.csv'
    if not csvpath.exists():ap.error('CSV principal não encontrado')
    catalog=load_csv(csvpath);byid={str(x.get('id_mensagem','')):x for x in catalog}
    # Instala o atualizador no projeto e mantém a integração quando o HTML for regenerado.
    installed=root/'scripts'/'check_epub_consolidar.py'
    if Path(__file__).resolve()!=installed.resolve():shutil.copy2(Path(__file__).resolve(),installed)
    gen=root/'scripts'/'gerar_relatorio_telegram.py'
    hook='# CHECK_EPUB_INTEGRACAO_V1'
    if gen.exists():
        src=gen.read_text(encoding='utf-8')
        if hook not in src:
            needle='    destination.write_text(html, encoding="utf-8")'
            if needle in src:
                src=src.replace(needle,needle+'''
    # CHECK_EPUB_INTEGRACAO_V1
    import subprocess as _ce_subprocess, sys as _ce_sys
    if (ROOT / "output" / "check_epub_varredura.json").exists():
        _ce_subprocess.run([_ce_sys.executable, str(ROOT / "scripts" / "check_epub_consolidar.py"),
                           "--projeto", str(ROOT), "--somente-html"], check=True)''',1)
                gen.write_text(src,encoding='utf-8')
            else:print('AVISO: gerador HTML não reconhecido; integração futura não instalada')
    if args.somente_html:
        if not scanfile.exists():ap.error('Varredura anterior não encontrada')
        scanned=json.loads(scanfile.read_text(encoding='utf-8'))['arquivos']
    else:
        folder=args.epubs.expanduser().resolve() if args.epubs else None
        paths=find_epubs(folder)
        if not paths:print('AVISO: nenhum EPUB encontrado. Para varrer, informe --epubs /caminho/para/EPUBs')
        scanned=[extract_epub(p) for p in paths]
        scanfile.write_text(json.dumps({'gerado_em':datetime.now().isoformat(),'raiz':str(folder or ''),'arquivos':scanned},ensure_ascii=False,indent=2),encoding='utf-8')
    # Older scan manifests may include macOS AppleDouble sidecars.
    scanned=[r for r in scanned if not is_sidecar(r)]
    candidates=candidates_lookup(root)
    for r in scanned:
        m=re.match(r'^(\d{4,9})[_ -]',r['arquivo'])
        r['id_mensagem']=m.group(1) if m else ''
        entry=byid.get(r['id_mensagem'],{})
        if not entry:
            # Only use basename matching when unique; avoid false association.
            matches=[x for x in catalog if x.get('nome_arquivo')==r['arquivo']]
            if len(matches)==1:entry=matches[0];r['id_mensagem']=str(entry.get('id_mensagem',''))
        r['status_catalogo']=entry.get('status_verificacao','')
        r['titulo_catalogo']=entry.get('titulo_catalogo','')
        r['autor_catalogo']=entry.get('autor_catalogo','')
        r['nacionalidade_catalogo_conhecida']=nationality_known(entry)
        r['candidatos_serper']=candidates.get(r['id_mensagem'],{}).get('candidatos',[])
    groups=consolidate_volumes(grouping(scanned))
    works=[];pending=[];duplicates=[];problems=[];uncertain=0
    for key,rs in groups.items():
        first=next((r for r in rs if trustworthy(r.get('titulo'))),rs[0])
        title=first.get('titulo') if trustworthy(first.get('titulo')) else title_guess(first['arquivo'])
        volume_bases={volume_key(r) for r in rs if volume_key(r)}
        if len(volume_bases)==1 and any(_VOLUME_MARKER.search(Path(r.get('arquivo','')).stem) for r in rs):
            title=_VOLUME_MARKER.sub('', str(title)).strip(' -_.,') or title
        links=sorted(set(u for r in rs for u in r['links']))
        nu=any('novelupdates.com/series/' in u.lower() for u in links)
        origin_known=any(r.get('nacionalidade_catalogo_conhecida') for r in rs)
        known=any('exata' in norm(r.get('status_catalogo','')) or 'identificad' in norm(r.get('status_catalogo','')) for r in rs)
        authors=list(dict.fromkeys(a for r in rs for a in r['autores'] if trustworthy(a)))
        errors=[r['arquivo']+': '+r['erro'] for r in rs if r['erro']]
        alt_titles=list(dict.fromkeys(v for r in rs for v in (r.get('titulo_catalogo'),r.get('titulo_normalizado'),r.get('titulo')) if trustworthy(v) and v!=title))
        obj={'chave':key,'titulo':title,'titulos_alternativos':alt_titles,'autores':authors,'arquivos':[r['arquivo'] for r in rs], 'quantidade':len(rs),'links':links,'erros':errors,'ids':[r['id_mensagem'] for r in rs], 'identificada':known,'nacionalidade_conhecida':origin_known,'tem_link_nu':nu,'candidatos_serper':sum(len(r['candidatos_serper']) for r in rs)}
        if not origin_known:works.append(obj)
        if len(rs)>1:duplicates.append(obj)
        if not known:pending.append(obj)
        # No proof of exhausted remedies or lack of alternate copies from partial ZIP / downloads.
        if errors:uncertain+=1
    identified=defaultdict(list)
    for row in catalog:
        if 'exata' not in norm(row.get('status_verificacao','')):continue
        t=norm(row.get('titulo_catalogo',''));a=norm(row.get('autor_catalogo',''))
        if t and a:identified[(t,a)].append({'id':row.get('id_mensagem',''),'arquivo':row.get('nome_arquivo','')})
    catalog_duplicates=[{'titulo_normalizado':k[0],'autor_normalizado':k[1],'registros':v} for k,v in identified.items() if len(v)>1]
    payload={'duplicatas_identificadas_catalogo':catalog_duplicates,'gerado_em':datetime.now().isoformat(),'total_arquivos':len(scanned),'obras':works,'pendentes':pending,'duplicatas':duplicates,'problemas':problems,'problemas_indeterminados':uncertain}
    prior=out/'check_epub_obras.json'
    if prior.exists():
        previous=json.loads(prior.read_text(encoding='utf-8'))
        reviews={tuple(sorted(row.get('arquivos',[]))):row['verificacao_obra']
                 for row in previous.get('obras',[]) if row.get('verificacao_obra')}
        previous_by_files={tuple(sorted(row.get('arquivos',[]))):row
                           for row in previous.get('obras',[])}
        for row in works:
            file_key=tuple(sorted(row.get('arquivos',[])))
            review=reviews.get(file_key)
            if review:row['verificacao_obra']=review
            curated=previous_by_files.get(file_key,{})
            for field in ('titulo','titulos_alternativos','autores'):
                value=curated.get(field)
                if value:row[field]=value
    for work in payload.get('obras',[]):
        apply_cheonchusein_work(work)
        apply_zhichu_survivorship_work(work)
        apply_verified_title_corrections_work(work)
    (out/'check_epub_obras.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    report=out/'relatorio_telegram.html'
    if report.exists():
        old=report.read_text(encoding='utf-8')
        # Existing generated HTML may contain previous CE panel; strip it before injecting.
        backup=report.with_suffix('.html.bak_check_epub')
        if '<!-- CHECK_EPUB_EXTRA_START -->' in old and backup.exists():
            candidate=backup.read_text(encoding='utf-8')
            required=('id="primaryTabs"','</nav>','</main>','</body>','const DATA=')
            if all(token in candidate for token in required):
                old=candidate
            else:
                # Backup antigo incompleto: reconstruir a base a partir do HTML atual.
                # Nunca sobrescrever nem apagar o backup original.
                import re as _ce_re
                for a,b in (
                    ('<!-- CHECK_EPUB_OFICIAL_START -->','<!-- CHECK_EPUB_OFICIAL_END -->'),
                    ('<!-- CHECK_EPUB_EXTRA_START -->','<!-- CHECK_EPUB_EXTRA_END -->'),
                    ('<!-- CHECK_EPUB_SECTIONS_START -->','<!-- CHECK_EPUB_SECTIONS_END -->'),
                    ('<!-- CHECK_EPUB_NAV_START -->','<!-- CHECK_EPUB_NAV_END -->'),
                ):
                    old=_ce_re.sub(_ce_re.escape(a)+r'.*?'+_ce_re.escape(b),'',old,flags=_ce_re.S)
                old=_ce_re.sub(r'<!-- CHECK_EPUB_OFICIAL_NAV --><button[^>]*id="nav-oficial".*?</button>','',old,flags=_ce_re.S)
                if not all(token in old for token in required):
                    raise ValueError('Nao foi possivel reconstruir HTML base; arquivos preservados')
                print('AVISO: backup HTML legado invalido; base recuperada do relatorio existente')
        if not backup.exists():shutil.copy2(report,backup)
        report.write_text(inject_html(old,payload,root),encoding='utf-8')
        # CHECK_EPUB_OFICIAL_INTEGRACAO_V1
        import subprocess as _of_subprocess
        _of_subprocess.run([sys.executable, str(root/'scripts'/'check_epub_oficial.py'),
                            '--projeto', str(root)], check=True)
    doc=root/'CHECK_EPUB_ESTADO_DO_PROJETO.md'
    doc.write_text(f'''# Check EPUB — estado consolidado\n\nAtualizado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n## Objetivo e sequência\n\n1. Inventariar downloads locais e metadados EPUB (OPF e links XHTML).\n2. Agrupar cópias com evidência forte: SHA-256, identificadores NovelUpdates/JJWXC ou título+autor iguais.\n3. Preservar homônimos, edições e volumes ambíguos para cruzamento posterior.\n4. Somente depois pesquisar na Serper os casos ainda sem referência suficiente.\n\n## Entradas e saídas\n\n- Catálogo principal (somente leitura): `output/telegram_midias_apenas_epub_origens_v3_ptbr.csv` ({len(catalog)} registros).\n- Candidatos anteriores (somente leitura): `novelupdates_candidatos.json` ({len(candidates)} registros).\n- Varredura local: `output/check_epub_varredura.json` ({len(scanned)} arquivos).\n- Agrupamentos e evidências: `output/check_epub_obras.json` ({len(works)} grupos).\n- Painel offline: `output/relatorio_telegram.html`.\n- Backup do painel: `output/relatorio_telegram.html.bak_check_epub`.\n\n## Resumo desta execução\n\n- EPUBs locais varridos: **{len(scanned)}**.\n- Agrupamentos conservadores: **{len(works)}**.\n- Grupos de duplicatas com evidência (EPUBs baixados): **{len(duplicates)}**.\n- Grupos de possíveis duplicatas entre os já identificados no catálogo (título+autor): **{len(catalog_duplicates)}**.\n- Grupos baixados sem identificação confirmada (inclusive com URL NU ainda não validada): **{len(pending)}**.\n- Problemas comprovadamente sem solução: **não apurados**; requer histórico completo das ações e alternativas.\n- EPUBs com falha de leitura: **{sum(bool(r['erro']) for r in scanned)}**.\n\n## Regras e limitações\n\n- Um link interno é evidência/candidato, não confirmação definitiva de identidade.\n- A falta de um link não prova que a obra não existe no NovelUpdates.\n- Duplicação de título sem autor ou identificador não prova duplicação de obra.\n- A classificação 'problemas sem solução' exige histórico de tentativas e alternativas, não inferível apenas do CSV.\n- Nenhum EPUB, catálogo ou manifesto de downloads é alterado.\n- A varredura só cobre os EPUBs existentes na pasta indicada por `--epubs`.\n\n## Execução\n\n```bash\ncd ~/Documents/TI/Projetos/Extract_txt\npython3 ~/Downloads/check_epub_consolidar.py --projeto . --epubs /Volumes/Seagate2T/old/Check_Epub\n```\n\n## Pendências\n\n- Verificar a cobertura da pasta de downloads e os resultados do agrupamento.\n- Cruzar posteriormente metadados internos com candidatos do NovelUpdates.\n- Integrar o histórico das ações anteriores para comprovar falhas irrecuperáveis.\n''',encoding='utf-8')
    print('EPUBs varridos:',len(scanned),'| grupos:',len(works),'| duplicatas:',len(duplicates),'| pendentes:',len(pending))
    print('Documentação:',doc);print('Relatório:',report)

if __name__=='__main__':main()

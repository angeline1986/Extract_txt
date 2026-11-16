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
    host=urlparse(str(url or '')).netloc.lower().split(':')[0]
    host=host.removeprefix('www.')
    known={
        'novelupdates.com':'Novel Updates',
        'jjwxc.net':'JJWXC',
        'ridibooks.com':'RIDI Books',
        'sevenseasentertainment.com':'Seven Seas',
        'yenpress.com':'Yen Press',
        'penguinrandomhouse.com':'Penguin Random House',
        'goodreads.com':'Goodreads',
        'books.google.com':'Google Books',
        'google.com':'Google Books',
        'mebmarket.com':'MEB Market',
        'fanqienovel.com':'Fanqie Novel',
        'webnovel.com':'Webnovel',
        'wattpad.com':'Wattpad',
        'tappytoon.com':'Tappytoon',
        'wtr-lab.com':'WTR-Lab',
        'chrysanthemumgarden.com':'Chrysanthemum Garden',
        'kadokawa-anime.com':'KADOKAWA',
        'mementobl.com':'MeMento',
        'vialactea.ca':'Via Lactea',
        'github.com':'Catálogo de obras',
    }
    for domain,label in known.items():
        if host==domain or host.endswith('.'+domain):return label
    if not host:return ''
    if host.endswith('wordpress.com'):
        return host.split('.')[0].replace('-',' ').title()+' (WordPress)'
    return host.removeprefix('m.').replace('-',' ').title()

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
    "Trash of the Count's Family": ('obra_00103','obra_00104','obra_00114','obra_00759','obra_00946','obra_02567'),
    'Raven of the Inner Palace': ('obra_00102','obra_00124'),
    'The Case Files of Jeweler Richard': ('obra_00132','obra_00133','obra_02495','obra_02736'),
    'I Can Do It': ('obra_00173','obra_00174','obra_02024'),
    'The Perfect Destiny': ('obra_00078','obra_00159'),
    'KinnPorsche': ('obra_00079','obra_00080'),
    "The Legendary Master's Wife": ('obra_00083','obra_00084','obra_00085','obra_00086','obra_00087'),
    'Little Mushroom': ('obra_00127','obra_00128'),
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

def inject_html(original, payload):
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
    confirmed_files=set();confirmed_epub_ids=set();country_counts=Counter()
    confirmed_work_keys=set()
    display_payload=presentation_obras(payload)
    display_rows=display_payload.get('obras',[])
    records_by_id={str(record.get('id','')):record for record in report_data.get('records',[])}
    for record in report_data.get('records',[]):
        if record.get('status')=='identificado':
            record['localizada_em']='Catálogo de obras (correspondência exata)'
        elif record.get('status')=='revisar':
            record['localizada_em']='Catálogo de obras (correspondência a revisar)'
        elif record.get('status')=='nao_encontrado':
            record['localizada_em']='Não encontrada no catálogo'
        else:
            record['localizada_em']='Sem confirmação no catálogo'
    def known_review(review):
        nationality=str((review or {}).get('nacionalidade_obra') or '').strip()
        return nationality.casefold() not in {
            '', 'pendente', 'não identificada', 'nao identificada',
            'desconhecida', 'unknown', 'unknown nationality'
        }
    for work in payload.get('obras',[]):
        review=work.get('verificacao_obra') or {}
        if not review:continue
        is_confirmed=known_review(review)
        nationality=str(review.get('nacionalidade_obra') or 'Pendente').strip()
        filenames=review.get('epubs_lidos') or work.get('arquivos',[])
        for filename in filenames:
            filename=str(filename)
            if is_confirmed:confirmed_files.add(filename)
            match=re.match(r'^(\d{1,9})[_\s-]',Path(filename).name)
            record_id=match.group(1) if match else ''
            record=records_by_id.get(record_id)
            if not record:continue
            refs=review.get('referencias') or []
            sources=list(dict.fromkeys(filter(None,(identification_source(ref) for ref in refs))))
            found_at=' + '.join(sources[:3]) if sources else 'EPUB'
            if len(sources)>3:found_at+=' + outras fontes'
            record.update({
                'obra_verificada':work.get('titulo',''),
                'autor_obra':review.get('autor',''),
                'nacionalidade_obra':nationality,
                'protagonistas_obra':review.get('protagonistas',[]),
                'verificadas':review.get('verificado_em',''),
                'localizada_em':found_at,
                'referencia_obra':(review.get('referencias') or [''])[0],
            })
            if is_confirmed:confirmed_epub_ids.add(record_id)
    # Count reviewed works using the same presentation grouping as Obras.
    # The EPUB count below still counts every associated file in the Explorer.
    for work in display_rows:
        review=work.get('verificacao_obra') or {}
        if not known_review(review):continue
        nationality=str(review.get('nacionalidade_obra') or 'Pendente').strip()
        country_counts[nationality]+=1
        confirmed_work_keys.add(str(work.get('chave') or work.get('titulo') or ''))
    report_data['obra_origins']={
        'work_count':len(confirmed_work_keys),
        'epub_count':len(confirmed_epub_ids),
        'countries':dict(country_counts),
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
    nav='''<button class="nav" id="nav-works" onclick="ceNavigate('works')" title="Obras"><span class="navicon">▤</span><span class="navlabel">Obras</span></button>
<button class="nav" id="nav-pending" onclick="ceNavigate('pending')" title="Baixadas não identificadas"><span class="navicon">⌕</span><span class="navlabel">Baixadas não identificadas</span></button>
<button class="nav" id="nav-problems" onclick="ceNavigate('problems')" title="Problemas sem solução"><span class="navicon">!</span><span class="navlabel">Problemas sem solução</span></button>
<button class="nav" id="nav-duplicates" onclick="ceNavigate('duplicates')" title="Duplicatas"><span class="navicon">▣</span><span class="navlabel">Duplicatas</span></button>'''
    if '</aside>' not in original or '</main>' not in original or '</body>' not in original:raise ValueError('Estrutura HTML inesperada; não alterada')
    original=original.replace('</aside>','<!-- CHECK_EPUB_NAV_START -->\n'+nav+'\n<!-- CHECK_EPUB_NAV_END -->\n</aside>',1)
    sections='''<!-- CHECK_EPUB_SECTIONS_START -->
<section id="works" class="hidden"><div class="eyebrow">Biblioteca / Obras</div><h1>Obras</h1><p class="sub">Obras em revisão, com autoria, origem e personagens conferidos nos EPUBs.</p><div class="panel"><input id="ce-search" placeholder="Buscar título, autor, protagonista ou arquivo" oninput="cePage=0;ceRender()" style="width:100%;padding:12px;margin-bottom:14px;border:1px solid #ddd;border-radius:8px"><div id="ce-works"></div></div></section>
<section id="pending" class="hidden"><div class="eyebrow">Biblioteca / Varredura local</div><h1>Baixadas não identificadas</h1><p class="sub">Obras baixadas ainda sem identificação confirmada, sem repetir cópias idênticas.</p><div class="panel" id="ce-pending"></div></section>
<section id="problems" class="hidden"><div class="eyebrow">Biblioteca / Pendências</div><h1>Problemas sem solução</h1><p class="sub">Somente falhas comprovadas sem outra cópia correspondente; situações não verificáveis permanecem separadas.</p><div class="panel" id="ce-problems"></div></section>
<section id="duplicates" class="hidden"><div class="eyebrow">Biblioteca / Auditoria</div><h1>Duplicatas</h1><p class="sub">Cópias idênticas e agrupamentos com evidência; títulos iguais sem autor não são mesclados automaticamente.</p><div class="panel" id="ce-duplicates"></div></section>
<!-- CHECK_EPUB_SECTIONS_END -->'''
    original=original.replace('</main>',sections+'\n</main>',1)
    js='''<script>
const CE_DATA=__CE_PAYLOAD__;
const ceEsc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function ceVerifiedLabel(value){const m=String(value||'').match(/^(\\d{4})-(\\d{2})-(\\d{2})(?:[T ](\\d{2}):(\\d{2}):(\\d{2}))?/);return m?m[3]+'/'+m[2]+'/'+m[1]+' '+(m[4]||'00')+':'+(m[5]||'00')+':'+(m[6]||'00'):(value||'Pendente');}
const ceViews=['overview','explorer','works','pending','problems','duplicates'];
function ceNavigate(v){if(!ceViews.includes(v))v='overview';ceViews.forEach(n=>{document.getElementById(n)?.classList.toggle('hidden',n!==v);document.getElementById('nav-'+n)?.classList.toggle('active',n===v)});location.hash=v;}
const ceOriginalNavigate=navigate;
navigate=ceNavigate;
let cePage=0;const cePageSize=50;
function ceDetails(g){if(g.itens_serie?.length)return g.itens_serie.map(v=>'<div style="padding:8px 0;border-bottom:1px solid #eee"><strong>'+ceEsc(v.titulo)+'</strong>'+(v.categoria?'<div>Categoria: '+ceEsc(v.categoria)+'</div>':'')+'<div>Autor: '+ceEsc(v.autores.join(', ')||'Não informado')+'</div>'+v.arquivos.map(f=>'<div>Arquivo: '+ceEsc(f)+'</div>').join('')+'</div>').join('');return g.arquivos.map(f=>'<div style="padding:5px 0">'+ceEsc(f)+'</div>').join('');}
function ceTable(items,obrasMode=false){if(!items.length)return '<p class="muted">Nenhum registro disponível nesta categoria.</p>';
const detailsHeader=obrasMode?'':'<th>Detalhes</th>';
const reviewHeaders=obrasMode?'<th>Nacionalidade da obra</th><th>Protagonistas</th>':'';
const refHeader=obrasMode?'<th>Referência</th>':'';
return '<div class="tablewrap"><table><thead><tr><th>Obra</th><th>Autor</th>'+reviewHeaders+(obrasMode?'<th>Verificadas</th>':'')+'<th>Arquivos</th>'+refHeader+detailsHeader+'</tr></thead><tbody>'+items.map(g=>{let v=g.verificacao_obra||{};let author=obrasMode&&v.autor?v.autor:(g.autores.join(', ')||'Não informado');let ref=(v.referencias||[])[0];return '<tr><td><strong>'+ceEsc(g.titulo)+'</strong></td><td>'+ceEsc(author)+'</td>'+(obrasMode?'<td>'+ceEsc(v.nacionalidade_obra||'Pendente')+'</td><td>'+ceEsc((v.protagonistas||[]).join(' / ')||'Pendente')+'</td><td>'+ceEsc(ceVerifiedLabel(v.verificado_em))+'</td>':'')+'<td>'+g.quantidade+'</td>'+(obrasMode?'<td>'+(ref?'<a href="'+ceEsc(ref)+'" target="_blank" rel="noopener noreferrer">Abrir</a>':'—')+'</td>':'<td><details><summary style="cursor:pointer;color:#3457a5">Ver arquivos associados</summary><div style="padding:10px 0;max-width:550px">'+ceDetails(g)+'</div></details></td>')+'</tr>'}).join('')+'</tbody></table></div>';
}
function ceRender(){let q=(document.getElementById('ce-search')?.value||'').trim().toLowerCase();let works=CE_DATA.obras.filter(g=>!g.nacionalidade_confirmada&&[g.titulo,...g.titulos_alternativos,...g.autores,...g.arquivos,...(g.verificacao_obra?.protagonistas||[]),g.verificacao_obra?.autor||'',g.verificacao_obra?.nacionalidade_obra||'',JSON.stringify(g.itens_serie||[])].join(' ').toLowerCase().includes(q)).sort((a,b)=>a.titulo.localeCompare(b.titulo,'pt-BR',{sensitivity:'base'}));
let pages=Math.max(1,Math.ceil(works.length/cePageSize));cePage=Math.min(cePage,pages-1);let shown=works.slice(cePage*cePageSize,(cePage+1)*cePageSize);
document.getElementById('ce-works').innerHTML='<p class="muted">'+works.length+' obras exibidas · '+CE_DATA.obras_transferidas+' transferidas ao Explorador por nacionalidade confirmada · '+CE_DATA.obras_revisadas_pendentes+' revisadas aguardando confirmação · '+CE_DATA.total_arquivos+' EPUBs válidos.</p>'+ceTable(shown,true)+'<div style="display:flex;justify-content:flex-end;align-items:center;gap:12px;margin-top:14px"><button type="button" onclick="ceMove(-1)" '+(cePage===0?'disabled':'')+'>Anterior</button><span class="muted">Página '+(cePage+1)+' de '+pages+'</span><button type="button" onclick="ceMove(1)" '+(cePage>=pages-1?'disabled':'')+'>Próximo</button></div>';
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
        for row in works:
            review=reviews.get(tuple(sorted(row.get('arquivos',[]))))
            if review:row['verificacao_obra']=review
    (out/'check_epub_obras.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    report=out/'relatorio_telegram.html'
    if report.exists():
        old=report.read_text(encoding='utf-8')
        # Existing generated HTML may contain previous CE panel; strip it before injecting.
        backup=report.with_suffix('.html.bak_check_epub')
        if '<!-- CHECK_EPUB_EXTRA_START -->' in old and backup.exists():
            old=backup.read_text(encoding='utf-8')
        if not backup.exists():shutil.copy2(report,backup)
        report.write_text(inject_html(old,payload),encoding='utf-8')
    doc=root/'CHECK_EPUB_ESTADO_DO_PROJETO.md'
    doc.write_text(f'''# Check EPUB — estado consolidado\n\nAtualizado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n## Objetivo e sequência\n\n1. Inventariar downloads locais e metadados EPUB (OPF e links XHTML).\n2. Agrupar cópias com evidência forte: SHA-256, identificadores NovelUpdates/JJWXC ou título+autor iguais.\n3. Preservar homônimos, edições e volumes ambíguos para cruzamento posterior.\n4. Somente depois pesquisar na Serper os casos ainda sem referência suficiente.\n\n## Entradas e saídas\n\n- Catálogo principal (somente leitura): `output/telegram_midias_apenas_epub_origens_v3_ptbr.csv` ({len(catalog)} registros).\n- Candidatos anteriores (somente leitura): `novelupdates_candidatos.json` ({len(candidates)} registros).\n- Varredura local: `output/check_epub_varredura.json` ({len(scanned)} arquivos).\n- Agrupamentos e evidências: `output/check_epub_obras.json` ({len(works)} grupos).\n- Painel offline: `output/relatorio_telegram.html`.\n- Backup do painel: `output/relatorio_telegram.html.bak_check_epub`.\n\n## Resumo desta execução\n\n- EPUBs locais varridos: **{len(scanned)}**.\n- Agrupamentos conservadores: **{len(works)}**.\n- Grupos de duplicatas com evidência (EPUBs baixados): **{len(duplicates)}**.\n- Grupos de possíveis duplicatas entre os já identificados no catálogo (título+autor): **{len(catalog_duplicates)}**.\n- Grupos baixados sem identificação confirmada (inclusive com URL NU ainda não validada): **{len(pending)}**.\n- Problemas comprovadamente sem solução: **não apurados**; requer histórico completo das ações e alternativas.\n- EPUBs com falha de leitura: **{sum(bool(r['erro']) for r in scanned)}**.\n\n## Regras e limitações\n\n- Um link interno é evidência/candidato, não confirmação definitiva de identidade.\n- A falta de um link não prova que a obra não existe no NovelUpdates.\n- Duplicação de título sem autor ou identificador não prova duplicação de obra.\n- A classificação 'problemas sem solução' exige histórico de tentativas e alternativas, não inferível apenas do CSV.\n- Nenhum EPUB, catálogo ou manifesto de downloads é alterado.\n- A varredura só cobre os EPUBs existentes na pasta indicada por `--epubs`.\n\n## Execução\n\n```bash\ncd ~/Documents/TI/Projetos/Extract_txt\npython3 ~/Downloads/check_epub_consolidar.py --projeto . --epubs /Volumes/Seagate2T/old/Check_Epub\n```\n\n## Pendências\n\n- Verificar a cobertura da pasta de downloads e os resultados do agrupamento.\n- Cruzar posteriormente metadados internos com candidatos do NovelUpdates.\n- Integrar o histórico das ações anteriores para comprovar falhas irrecuperáveis.\n''',encoding='utf-8')
    print('EPUBs varridos:',len(scanned),'| grupos:',len(works),'| duplicatas:',len(duplicates),'| pendentes:',len(pending))
    print('Documentação:',doc);print('Relatório:',report)

if __name__=='__main__':main()

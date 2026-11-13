#!/usr/bin/env python3
"""Classifica origem de obras de CSV Telegram usando evidências públicas.
Dependências: python3 -m pip install requests
Uso: python3 classificar_origem_novels.py --csv /caminho/telegram_midias_apenas_epub.csv
"""
import argparse, csv, difflib, json, re, sys, time, unicodedata
from pathlib import Path
from urllib.parse import quote
import requests

HEADERS = {'User-Agent':'NovelOriginAudit/1.0 (personal catalog metadata; requests library)'}
COUNTRY_MAP = {
 'china':'CN','people’s republic of china':'CN',"people's republic of china":'CN',
 'republic of china':'TW','taiwan':'TW','south korea':'KR','republic of korea':'KR',
 'japan':'JP','united states':'US','united kingdom':'GB','thailand':'TH',
 'vietnam':'VN','indonesia':'ID','russia':'RU','france':'FR',
}
LANGUAGE_MAP = {'chinese':'CN','mandarin chinese':'CN','japanese':'JP','korean':'KR'}
FIELDS = ['titulo_normalizado','pais_origem','idioma_original','confianca','status_verificacao','fonte_verificacao','evidencia','url_pesquisa']


def normalize(s):
    s = unicodedata.normalize('NFKC', s).lower()
    s = re.sub(r'\.epub$', '', s, flags=re.I)
    s = s.replace('_',' ')
    s = re.sub(r'\([^)]*(?:\bcn\b|\bmtl\b|\bvol\b|\bchapters?\b|\b1lib\b)[^)]*\)', ' ', s, flags=re.I)
    s = re.sub(r'\b(?:chapters?|vol(?:ume)?|mtl|z library|1lib|epub)\b.*$', '', s, flags=re.I)
    s = re.sub(r'\s+', ' ', s).strip(' -.,')
    return s


def ascii_key(s):
    s = unicodedata.normalize('NFKD',s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^\w\u3400-\u9fff\uac00-\ud7af]+',' ',s.casefold()).strip()


def api(session,url,params,delay):
    time.sleep(delay)
    for attempt in range(3):
        try:
            r = session.get(url,params=params,timeout=18)
            if r.status_code in (429,500,502,503,504):
                time.sleep(2*(attempt+1)); continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException,ValueError):
            if attempt < 2: time.sleep(2*(attempt+1))
    return None


def wd_labels(session, ids, lang, delay):
    if not ids: return {}
    data = api(session,'https://www.wikidata.org/w/api.php',
        {'action':'wbgetentities','ids':'|'.join(ids[:40]),'props':'labels','languages':lang+'|en','format':'json'},delay)
    if not data: return {}
    out = {}
    for qid,ent in data.get('entities',{}).items():
        labels=ent.get('labels',{})
        out[qid]=(labels.get(lang) or labels.get('en') or {}).get('value','')
    return out


def claim_ids(ent,prop):
    out=[]
    for cl in ent.get('claims',{}).get(prop,[]):
        if cl.get('rank')=='deprecated':continue
        val=cl.get('mainsnak',{}).get('datavalue',{}).get('value')
        if isinstance(val,dict) and val.get('id'):out.append(val['id'])
    return out


def wikidata_lookup(session,title,delay):
    search=api(session,'https://www.wikidata.org/w/api.php',
        {'action':'wbsearchentities','search':title,'language':'en','format':'json','limit':8},delay)
    if not search:return None
    hits=search.get('search',[])
    if not hits:return None
    names=[(x.get('id'),x.get('label',''),x.get('description','')) for x in hits]
    scored=sorted(names,key=lambda x:difflib.SequenceMatcher(None,ascii_key(title),ascii_key(x[1])).ratio(),reverse=True)
    ids=[x[0] for x in scored[:4] if x[0]]
    data=api(session,'https://www.wikidata.org/w/api.php',
        {'action':'wbgetentities','ids':'|'.join(ids),'props':'claims|labels','languages':'en','format':'json'},delay)
    if not data:return None
    for qid,label,description in scored[:4]:
        similarity=difflib.SequenceMatcher(None,ascii_key(title),ascii_key(label)).ratio()
        if similarity<0.91:continue
        ent=data.get('entities',{}).get(qid,{})
        country_ids=claim_ids(ent,'P495') # country of origin
        language_ids=claim_ids(ent,'P364') # original language of film or TV show; for literary works may not exist
        if not language_ids: language_ids=claim_ids(ent,'P407') # language of work
        names_map=wd_labels(session,country_ids+language_ids,'en',delay)
        countries=[names_map.get(i,'') for i in country_ids]
        languages=[names_map.get(i,'') for i in language_ids]
        codes=[COUNTRY_MAP[c.casefold()] for c in countries if c.casefold() in COUNTRY_MAP]
        if codes and len(set(codes))==1:
            return {'pais_origem':codes[0],'idioma_original':'; '.join(languages),
                    'confianca':'alta' if similarity>=0.98 else 'media',
                    'status_verificacao':'confirmado_por_metadado',
                    'fonte_verificacao':f'https://www.wikidata.org/wiki/{qid}',
                    'evidencia':f'Wikidata P495 (país de origem): {"; ".join(countries)}; título: {label}'}
        # No country-of-origin claim: never infer nationality solely from language.
    return None


def main():
    parser=argparse.ArgumentParser(description='Pesquisa origem de obras EPUB com evidências verificáveis')
    parser.add_argument('--csv',type=Path,required=True)
    parser.add_argument('--saida',type=Path,default=None)
    parser.add_argument('--intervalo',type=float,default=0.6,help='Pausa entre chamadas HTTP (segundos)')
    args=parser.parse_args()
    if not args.csv.is_file():sys.exit(f'CSV não encontrado: {args.csv}')
    output=args.saida or args.csv.with_name(args.csv.stem+'_origens.csv')
    cachefile=output.with_suffix('.cache.json')
    try:cache=json.loads(cachefile.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):cache={}
    with args.csv.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or 'nome_arquivo' not in reader.fieldnames:
            sys.exit('CSV precisa conter coluna nome_arquivo')
        columns=list(dict.fromkeys(reader.fieldnames+FIELDS))
        rows=[r for r in reader if (r.get('nome_arquivo') or '').strip().lower().endswith('.epub')]
    session=requests.Session();session.headers.update(HEADERS)
    titles={ascii_key(normalize(r['nome_arquivo'])):normalize(r['nome_arquivo']) for r in rows}
    print(f'{len(rows)} arquivos EPUB, {len(titles)} títulos normalizados (aproximadamente).',flush=True)
    for idx,(key,title) in enumerate(titles.items(),1):
        if key in cache:continue
        print(f'[{idx}/{len(titles)}] {title[:85]}',flush=True)
        result=wikidata_lookup(session,title,args.intervalo)
        if not result:
            result={'pais_origem':'INDEFINIDO','idioma_original':'', 'confianca':'nenhuma',
                    'status_verificacao':'revisao_manual','fonte_verificacao':'',
                    'evidencia':'Não foi encontrada evidência inequívoca de país de origem em Wikidata'}
        result['url_pesquisa']='https://www.google.com/search?q='+quote('"'+title+'" novel original country site:novelupdates.com/series/')
        cache[key]=result
        cachefile.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')
    with output.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader()
        for row in rows:
            title=normalize(row['nome_arquivo']);row.update(cache[ascii_key(title)])
            row['titulo_normalizado']=title
            writer.writerow(row)
    confirmed=sum(1 for r in rows if cache[ascii_key(normalize(r['nome_arquivo']))]['pais_origem']!='INDEFINIDO')
    print(f'\nConcluído: {confirmed}/{len(rows)} arquivos classificados com evidência de país.')
    print('CSV:',output)
    print('Cache (permite retomar):',cachefile)
    print('INDEFINIDO significa não confirmado; não significa que a obra não seja CN/KR/JP.')

if __name__=='__main__':main()

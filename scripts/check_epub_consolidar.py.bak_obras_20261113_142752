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
    return sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.lower()=='.epub'),key=lambda p:str(p))

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

def grouping(records):
    """Never merge solely on vague similar titles: same normalized title AND compatible authors, or exact SHA/URL identifiers."""
    groups={}; bysha={}; byid={}; bytitle={}
    for r in records:
        key=None; sha=r.get('sha256','')
        ids=[]
        for u in r.get('links',[]):
            parsed=urlparse(u);host=parsed.netloc.lower().removeprefix('www.')
            if host=='novelupdates.com' and '/series/' in parsed.path:
                ids.append('nu:'+parsed.path.strip('/').lower())
            if host=='jjwxc.net' and 'novelid' in parse_qs(parsed.query):
                ids.append('jjwxc:'+parse_qs(parsed.query)['novelid'][0])
        for id_ in ids:
            if id_ in byid:key=byid[id_];break
        if key is None and sha and sha in bysha:key=bysha[sha]
        t=norm(r.get('titulo') or title_guess(r.get('arquivo','')))
        author=norm(' '.join(r.get('autores',[])))
        if key is None and t and author and (t,author) in bytitle:key=bytitle[(t,author)]
        if key is None:key='obra_'+str(len(groups)+1).zfill(5);groups[key]=[]
        groups[key].append(r)
        if sha:bysha[sha]=key
        for id_ in ids:byid[id_]=key
        if t and author:bytitle[(t,author)]=key
    return groups

def safe_json(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')

def inject_html(original, payload):
    start='<!-- CHECK_EPUB_EXTRA_START -->';end='<!-- CHECK_EPUB_EXTRA_END -->'
    original=re.sub(re.escape(start)+r'.*?'+re.escape(end),'',original,flags=re.S)
    nav='''<button class="nav" id="nav-works" onclick="ceNavigate('works')" title="Obras"><span class="navicon">▤</span><span class="navlabel">Obras</span></button>
<button class="nav" id="nav-pending" onclick="ceNavigate('pending')" title="Baixadas não identificadas"><span class="navicon">⌕</span><span class="navlabel">Baixadas não identificadas</span></button>
<button class="nav" id="nav-problems" onclick="ceNavigate('problems')" title="Problemas sem solução"><span class="navicon">!</span><span class="navlabel">Problemas sem solução</span></button>
<button class="nav" id="nav-duplicates" onclick="ceNavigate('duplicates')" title="Duplicatas"><span class="navicon">▣</span><span class="navlabel">Duplicatas</span></button>'''
    if '</aside>' not in original or '</main>' not in original or '</body>' not in original:raise ValueError('Estrutura HTML inesperada; não alterada')
    original=original.replace('</aside>',nav+'\n</aside>',1)
    sections='''<section id="works" class="hidden"><div class="eyebrow">Biblioteca / Obras</div><h1>Obras</h1><p class="sub">Agrupamentos conservadores: SHA-256, identificadores de origem ou título e autor idênticos.</p><div class="panel"><input id="ce-search" placeholder="Buscar obra, autor, arquivo ou URL" oninput="ceRender()" style="width:100%;padding:12px;margin-bottom:14px;border:1px solid #ddd;border-radius:8px"><div id="ce-works"></div></div></section>
<section id="pending" class="hidden"><div class="eyebrow">Biblioteca / Varredura local</div><h1>Baixadas não identificadas</h1><p class="sub">Obras baixadas ainda sem identificação confirmada, sem repetir cópias idênticas.</p><div class="panel" id="ce-pending"></div></section>
<section id="problems" class="hidden"><div class="eyebrow">Biblioteca / Pendências</div><h1>Problemas sem solução</h1><p class="sub">Somente falhas comprovadas sem outra cópia correspondente; situações não verificáveis permanecem separadas.</p><div class="panel" id="ce-problems"></div></section>
<section id="duplicates" class="hidden"><div class="eyebrow">Biblioteca / Auditoria</div><h1>Duplicatas</h1><p class="sub">Cópias idênticas e agrupamentos com evidência; títulos iguais sem autor não são mesclados automaticamente.</p><div class="panel" id="ce-duplicates"></div></section>'''
    original=original.replace('</main>',sections+'\n</main>',1)
    js='''<script>
const CE_DATA=__CE_PAYLOAD__;
const ceEsc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ceViews=['overview','explorer','works','pending','problems','duplicates'];
function ceNavigate(v){if(!ceViews.includes(v))v='overview';ceViews.forEach(n=>{document.getElementById(n)?.classList.toggle('hidden',n!==v);document.getElementById('nav-'+n)?.classList.toggle('active',n===v)});location.hash=v;}
const ceOriginalNavigate=navigate;
navigate=ceNavigate;
function ceTable(items){if(!items.length)return '<p class="muted">Nenhum registro disponível nesta categoria.</p>';
return '<div class="tablewrap"><table><thead><tr><th>Obra / arquivo</th><th>Autor</th><th>Arquivos</th><th>Evidências e links</th></tr></thead><tbody>'+items.map(g=>'<tr><td><strong>'+ceEsc(g.titulo)+'</strong><div class="muted">'+ceEsc(g.arquivos.slice(0,4).join(' · '))+'</div></td><td>'+ceEsc(g.autores.join(', ')||'Não informado')+'</td><td>'+g.quantidade+'</td><td>'+g.links.slice(0,6).map(u=>'<div><a href="'+ceEsc(u)+'" target="_blank" rel="noopener noreferrer">'+ceEsc(u.length>75?u.slice(0,75)+'…':u)+'</a></div>').join('')+(g.erros.length?'<div class="muted">'+ceEsc(g.erros.join('; '))+'</div>':'')+'</td></tr>').join('')+'</tbody></table></div>';}
function ceRender(){let q=(document.getElementById('ce-search')?.value||'').toLowerCase();let works=CE_DATA.obras.filter(g=>JSON.stringify(g).toLowerCase().includes(q));
document.getElementById('ce-works').innerHTML='<p class="muted">'+works.length+' obras agrupadas de '+CE_DATA.total_arquivos+' EPUBs varridos.</p>'+ceTable(works);
document.getElementById('ce-pending').innerHTML='<p class="muted">'+CE_DATA.pendentes.length+' agrupamentos pendentes. Identificação baseada apenas em evidências locais.</p>'+ceTable(CE_DATA.pendentes);
document.getElementById('ce-problems').innerHTML='<p class="muted">'+CE_DATA.problemas.length+' falhas sem alternativa comprovadas. '+CE_DATA.problemas_indeterminados+' casos não classificáveis por falta de histórico completo de tentativas.</p>'+ceTable(CE_DATA.problemas);
document.getElementById('ce-duplicates').innerHTML='<p class="muted">'+CE_DATA.duplicatas.length+' grupos com mais de um arquivo; '+CE_DATA.duplicatas_identificadas_catalogo.length+' grupos de título+autor repetidos entre os identificados no catálogo.</p>'+ceTable(CE_DATA.duplicatas);}
ceRender();ceNavigate(ceViews.includes(location.hash.slice(1))?location.hash.slice(1):'overview');
</script>'''.replace('__CE_PAYLOAD__',safe_json(payload))
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
        r['candidatos_serper']=candidates.get(r['id_mensagem'],{}).get('candidatos',[])
    groups=grouping(scanned)
    works=[];pending=[];duplicates=[];problems=[];uncertain=0
    for key,rs in groups.items():
        first=next((r for r in rs if r.get('titulo')),rs[0]); title=first.get('titulo') or title_guess(first['arquivo'])
        links=sorted(set(u for r in rs for u in r['links']))
        nu=any('novelupdates.com/series/' in u.lower() for u in links)
        known=any('exata' in norm(r.get('status_catalogo','')) or 'identificad' in norm(r.get('status_catalogo','')) for r in rs)
        authors=list(dict.fromkeys(a for r in rs for a in r['autores']))
        errors=[r['arquivo']+': '+r['erro'] for r in rs if r['erro']]
        obj={'chave':key,'titulo':title,'autores':authors,'arquivos':[r['arquivo'] for r in rs], 'quantidade':len(rs),'links':links,'erros':errors,'ids':[r['id_mensagem'] for r in rs], 'identificada':known,'tem_link_nu':nu,'candidatos_serper':sum(len(r['candidatos_serper']) for r in rs)}
        works.append(obj)
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

#!/usr/bin/env python3
"""Adiciona a seção Oficial ao painel Check Epub sem criar uma aba de navegação.

Uso: python3 scripts/check_epub_oficial.py --projeto .
O catálogo é resolvido no navegador a partir do DATA.records já integrado ao HTML.
Correspondências incertas permanecem separadas; podem ser confirmadas em
output/oficial_decisions.json, campo `merges` (listas de obra_chave).
"""
import argparse
import html
import json
import re
from pathlib import Path

START = '<!-- CHECK_EPUB_OFICIAL_START -->'
END = '<!-- CHECK_EPUB_OFICIAL_END -->'
NAV = '<!-- CHECK_EPUB_OFICIAL_NAV -->'

CSS = r'''<style id="ce-oficial-styles">
#oficial .of-filters{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}
#oficial .of-filters input{flex:1;min-width:220px}
#oficial .of-filters select,#oficial .of-filters input,#oficial .of-filters button{padding:10px;border-radius:8px;border:1px solid #dfe5ee;background:#fff;color:#26364d}
#oficial .of-meta{margin:12px 0;color:#64748b;font-size:13px}
#oficial .of-badge{display:inline-block;padding:3px 8px;border-radius:14px;background:#eef2ff;color:#3457a5;white-space:nowrap}
#oficial .of-pending{background:#fff3dc;color:#a66a09}
#oficial .of-table{min-width:780px}
#oficial .of-table th{color:#506482}
#oficial .of-table td{vertical-align:middle}
#oficial .of-detail{background:#f8fafc;padding:14px 20px;overflow-x:auto}
#oficial .of-detail table{min-width:740px}
#oficial .of-detail td{font-size:12px}
#oficial .of-warning{margin:8px 0;color:#9a6700;font-size:12px}
#oficial .of-summary{font-size:13px;color:#64748b;margin:0 0 12px}
</style>'''
SECTION = r'''<section id="oficial" class="hidden" aria-labelledby="nav-oficial">
<div class="eyebrow">Biblioteca / Catálogo independente</div>
<h1>Oficial</h1>
<p class="sub">Catálogo consolidado por identidade de obra. Agrupamentos ambíguos não são fundidos automaticamente.</p>
<div class="panel">
<div class="of-filters">
<input id="of-search" placeholder="Buscar obra, alias, autor ou arquivo" oninput="ofPage=0;ofRender()" aria-label="Buscar no catálogo Oficial">
<select id="of-country" onchange="ofPage=0;ofRender()" aria-label="Filtrar origem"><option value="">Todas as origens</option></select>
<select id="of-status" onchange="ofPage=0;ofRender()" aria-label="Filtrar situação do país"><option value="">Todas</option><option value="confirmada">País confirmado</option><option value="pendente">País não confirmado</option><option value="conflito">Conflito</option></select>
<button type="button" onclick="ofExport()">Exportar CSV</button>
</div>
<div id="of-summary" class="of-summary"></div>
<div class="tablewrap"><table class="of-table"><thead><tr><th>Obra</th><th>Autor</th><th>Protagonistas</th><th>Origem</th><th>EPUBs</th><th></th></tr></thead><tbody id="of-body"></tbody></table></div>
<div class="pagination"><span id="of-range"></span><div><button id="of-prev" onclick="ofPage--;ofRender()">Anterior</button> <button id="of-next" onclick="ofPage++;ofRender()">Próximo</button></div></div>
</div></section>'''
# JS separate isolated closure, controls only #oficial and #nav-oficial.
JS = r'''<script id="ce-oficial-script">
(function(){'use strict';
const $=id=>document.getElementById(id);
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=s=>String(s||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[’']/g,'').replace(/[^\p{L}\p{N}]+/gu,' ').trim().replace(/\s+/g,' ');
const pending=s=>{const value=norm(s);return !value||['pendente','indefinido','unknown','-'].includes(value)||value.startsWith('nao identificad')||value.startsWith('não identificad')||value.startsWith('internacional oel')||value.startsWith('fanfic ingles')};
const volume=s=>norm(String(s||'').replace(/\b(?:vol(?:ume)?|book|livro|tomo)\.?\s*\d+\b/ig,'').replace(/\b(?:chapters?|cap[ií]tulos?)\s*\d+\s*(?:[-–]\s*\d+)?\b/ig,''));
const items=(Array.isArray(window.DATA?.records)?window.DATA.records:typeof DATA!=='undefined'?DATA.records:[]).map(r=>({...r}));
const decisions=__DECISIONS__;
// CE_OFICIAL_SPECIFIC_OVERRIDES_V1
// Sobreposicoes sao limitadas a aba Oficial; nunca alteram window.DATA.
const officialRows=items;
const selectedOfficialOverrides=Array.isArray(decisions.overrides)?decisions.overrides:[];
for(const override of selectedOfficialOverrides){
  if(!override||override.match_title!=='For a Thousand Autumns')continue;
  const normalizeTitle=t=>String(t||'').normalize('NFKC').trim().toLowerCase();
  const matches=officialRows.filter(r=>
    String(r.id||'')===String(override.match_id||'72590')||
    [r.obra_verificada,r.catalogo,r.titulo].some(t=>['for a thousand autumns','for a thousand autums'].includes(normalizeTitle(t)))
  );
  // Nao alterar outros registros se houver ambiguidade.
  if(matches.length!==1){console.warn('Oficial: correcao pontual nao aplicada; registros encontrados:',matches.length);continue;}
  const r=matches[0];
  r.obra_chave='oficial:cheonchusein:for-a-thousand-autumns';
  r.obra_verificada='For a Thousand Autumns';
  r.titulo='For a Thousand Autumns';
  r.catalogo='For a Thousand Autumns';
  r.autor_obra='Lanmaru (novel), Gilmong e Boogie (arte)';
  r.protagonistas_obra=['Moonpyeong Seok','Demônio Celestial'];
  r.nacionalidade_obra='Coreia do Sul';
  r.titulo_original_obra='Cheonchusein (천추세인)';
  r.tipo_obra='Manhwa / Webtoon';
  r.sinopse_obra='Um membro de baixo escalão da Seita Demoníaca vira guarda-costas do líder em uma disputa de sucessão.';
  r.fonte_nacionalidade_obra='https://www.novelupdates.com/series/celestial/';
  r.referencia_obra='https://manta.net/en/series/for-a-thousand-autumns-full-ver?seriesId=3467';
  r.localizada_em='Manhwa / Webtoon: Cheonchusein';
  r.observacao_obra='Obra coreana distinta da novel chinesa Thousand Autumns / Qian Qiu; identidade e créditos conferidos no Manta e no Novel Updates.';
}
const byKey=new Map(),parent=new Map();
function keyOf(r,i){return String(r.obra_chave||'').trim()||'epub:'+String(r.id||i)}
function root(k){let p=parent.get(k)||k;if(p!==k){p=root(p);parent.set(k,p)}return p}
function union(a,b){a=root(a);b=root(b);if(a!==b)parent.set(b,a)}
items.forEach((r,i)=>{let k=keyOf(r,i);parent.set(k,k);if(!byKey.has(k))byKey.set(k,[]);byKey.get(k).push(r)});
// Explicitly approved equivalences; no fuzzy automatic union.
for(const group of decisions.merges||[]){if(!Array.isArray(group)||group.length<2)continue;const keys=group.map(String);if(keys.every(k=>byKey.has(k)))for(const k of keys.slice(1))union(keys[0],k)}
const canonical=(r)=>r.obra_verificada||r.catalogo||r.titulo||r.nome||'Sem título';
const author=(r)=>r.autor_obra||r.autor||'';
const country=(r)=>r.nacionalidade_obra||'';
// High-confidence deterministic grouping: same known series reference OR same title+author.
// A reference is trusted for equality only if it is a series page, never a generic site/author page.
function ref(r){const raw=String(r.referencia_obra||r.fonte_nacionalidade_obra||'');try{const u=new URL(raw);const h=u.hostname.replace(/^www\./,'').toLowerCase();const p=u.pathname.replace(/\/$/,'').toLowerCase();if(h==='novelupdates.com'&&/^\/series\/[^/]+$/.test(p))return h+p;if(h==='jjwxc.net'&&p.includes('onebook.php')&&u.searchParams.get('novelid'))return h+'/onebook.php?novelid='+u.searchParams.get('novelid');}catch(e){}return ''}
// Series/volume identity: grouping is allowed only with explicit volume evidence
// plus an author, or matching title-base, author AND protagonists for subtitles.
// Similarity alone never merges titles; "For a Thousand Autumns" is NOT an alias
// of "Thousand Autumns" merely because one title contains the other.
function volumeIdentity(title){
  const s=String(title||'').trim().replace(/^\d{4,9}[_\s-]+/u,'').replace(/\.epub$/iu,'');
  // [Assistant and the Villain 01] - Assistant to the Villain
  const bracket=s.match(/^\s*\[([^\]]+?)\s+(?:0?[1-9]|[1-9]\d+)(?:\s*[-–:]\s*[^\]]*)?\]\s*(?:[-–:]\s*.+)?$/u);
  if(bracket)return {base:norm(bracket[1]),kind:'numbered',evidence:s};
  // Kusunoki’s Garden of Gods, Vol. 1; Title - Volume 2 - Translator
  const m=s.match(/^(.+?)[\s,;:–-]+(?:vol(?:ume)?|book|livro|tomo)\.?\s*(\d+)(?:\b|$)/iu);
  if(m)return {base:norm(m[1]),kind:'numbered',evidence:s};
  return null;
}
function authorIdentity(rs){
  const values=[...new Set(rs.map(r=>norm(author(r))).filter(Boolean))];
  return values.length===1?values[0]:'';
}
function characterIdentity(rs){
  const values=[...new Set(rs.flatMap(r=>Array.isArray(r.protagonistas_obra)?r.protagonistas_obra:[]).map(norm).filter(Boolean))].sort();
  return values.length?values.join('|'):'';
}
function countryIdentity(rs){
  const values=[...new Set(rs.map(r=>norm(country(r))).filter(c=>c&&!pending(c)))];
  return values.length===1?values[0]:'';
}
function subtitleIdentity(t){
  // A title followed by a subtitle is merely a candidate; other metadata
  // must corroborate it. Do not strip arbitrary leading words (For, My, etc).
  const m=String(t||'').match(/^(.{9,}?)\s*:\s*([^:]+)$/u);
  return m?norm(m[1]):'';
}
const references=new Map(),exact=new Map(),numberedSeries=new Map();
for(const [key,rs] of byKey){
  const refs=new Set(rs.map(ref).filter(Boolean));
  for(const r of refs){if(references.has(r)){const other=references.get(r);if(identityCompatible(rs,byKey.get(other)))union(key,other)}else references.set(r,key)}
  const titles=new Set(rs.flatMap(r=>[canonical(r),r.catalogo,r.titulo].map(volume).filter(x=>x.length>=9)));
  const authors=new Set(rs.map(r=>norm(author(r))).filter(Boolean));
  if(authors.size===1){const a=[...authors][0];for(const t of titles){const k=t+'|'+a;if(exact.has(k)){const other=exact.get(k);if(identityCompatible(rs,byKey.get(other)))union(key,other)}else exact.set(k,key)}}
  const a=authorIdentity(rs);
  if(a){
    const explicit=rs.flatMap(r=>[canonical(r),r.catalogo,r.titulo,r.nome]).map(volumeIdentity).filter(x=>x&&x.base.length>=9);
    for(const v of explicit){
      const k=v.base+'|'+a;
      if(numberedSeries.has(k)){
        const other=numberedSeries.get(k);
        const c1=countryIdentity(rs),c2=countryIdentity(byKey.get(other));
        if((!c1||!c2||c1===c2)&&identityCompatible(rs,byKey.get(other)))union(key,other);
      }else numberedSeries.set(k,key);
    }
  }
}
// Associate an unnumbered base title with its numbered volumes using author
// and a matching base; never use generic fuzzy similarity.
for(const [key,rs] of byKey){
  const a=authorIdentity(rs);if(!a)continue;
  for(const r of rs){
    const t=norm(canonical(r));const seriesKey=t+'|'+a;
    const other=numberedSeries.get(seriesKey);
    if(other){const c1=countryIdentity(rs),c2=countryIdentity(byKey.get(other));if((!c1||!c2||c1===c2)&&identityCompatible(rs,byKey.get(other)))union(key,other)}
  }
}
// A colon subtitle can be grouped with its exact root only when the author,
// protagonists AND known nationality all agree (e.g. Thousand Autumns: Qian Qiu).
const bareTitles=new Map();
for(const [key,rs] of byKey){
  const a=authorIdentity(rs),p=characterIdentity(rs),c=countryIdentity(rs);
  if(!a||!p||!c)continue;
  for(const r of rs){const t=norm(canonical(r));if(t){const k=t+'|'+a+'|'+p+'|'+c;if(!bareTitles.has(k))bareTitles.set(k,key)}}
}
for(const [key,rs] of byKey){
  const a=authorIdentity(rs),p=characterIdentity(rs),c=countryIdentity(rs);
  if(!a||!p||!c)continue;
  for(const r of rs){const base=subtitleIdentity(canonical(r));if(!base)continue;
    const other=bareTitles.get(base+'|'+a+'|'+p+'|'+c);if(other&&identityCompatible(rs,byKey.get(other)))union(key,other);
  }
}
// CE_OFICIAL_SERIES_PRESENTATION_V2
function volumeInfo(value){
  const s=String(value||'').replace(/^\d{4,9}[_\s-]+/u,'').replace(/\.epub$/iu,'').trim();
  let m=s.match(/^\s*\[([^\]]+?)\s+(\d{1,3})(?:\s*[-–:]\s*[^\]]*)?\]\s*(?:[-–:]\s*(.+))?$/u);
  if(m)return {base:m[1].trim(),number:Number(m[2]),part:(m[3]||'').trim()};
  m=s.match(/^(.+?)[\s,;:–-]+(?:vol(?:ume)?|book|livro|tomo)\.?\s*(\d{1,3})(?:\b|$)/iu);
  if(m)return {base:m[1].trim().replace(/[\s,;:–-]+$/u,''),number:Number(m[2]),part:''};
  return null;
}
function seriesDisplay(g){
  const candidates=g.records.flatMap(r=>[r.obra_verificada,r.catalogo,r.titulo,r.nome]);
  const numbered=candidates.map(volumeInfo).filter(v=>v&&norm(v.base).length>=7);
  if(!numbered.length)return '';
  const tally=new Map();
  for(const v of numbered){const k=norm(v.base);const entry=tally.get(k)||{count:0,label:v.base};entry.count++;if(v.base.length<entry.label.length)entry.label=v.base;tally.set(k,entry)}
  const best=[...tally.values()].sort((a,b)=>b.count-a.count||a.label.length-b.label.length)[0];
  // Only use a common base when at least two EPUBs support it and it dominates.
  if(!best||g.records.length<2||best.count<2)return '';
  return best.label;
}
function volumeRow(r){
  for(const value of [r.obra_verificada,r.catalogo,r.titulo,r.nome]){
    const v=volumeInfo(value);if(v)return v;
  }
  return null;
}
function sortFiles(rs){
  return [...rs].sort((a,b)=>{
    const x=volumeRow(a),y=volumeRow(b);
    return (x?.number??99999)-(y?.number??99999)||String(a.nome||'').localeCompare(String(b.nome||''),'pt-BR',{numeric:true});
  });
}
// A different explicit series URL or contradictory known country is a review blocker.
// Use same-author gating for title/volume unions, but do not infer authors from names.
function normalizedAuthor(value){
 const first=String(value||'').split(/[\/;|]/u)[0].replace(/\([^)]*\)/gu,'').trim();
 // Transliteration may coexist with CJK script: "Meng Xi Shi (梦溪石)".
 return norm(first).replace(/[^a-z0-9 ]+/gu,'').trim();
}
function identityCompatible(a,b){
 const aa=authorIdentity(a),bb=authorIdentity(b);
 if(aa&&bb&&aa!==bb){
   const av=[...new Set(a.map(r=>normalizedAuthor(author(r))).filter(Boolean))];
   const bv=[...new Set(b.map(r=>normalizedAuthor(author(r))).filter(Boolean))];
   if(!av.length||!bv.length||!av.some(x=>bv.includes(x)&&x.length>=6))return false;
 }
 const ca=countryIdentity(a),cb=countryIdentity(b);
 if(ca&&cb&&ca!==cb)return false;
 const ra=new Set(a.map(ref).filter(Boolean)),rb=new Set(b.map(ref).filter(Boolean));
 if(ra.size&&rb.size&&![...ra].some(u=>rb.has(u)))return false;
 return true;
}

const groups=new Map();for(const [key,rs] of byKey){const k=root(key);if(!groups.has(k))groups.set(k,{keys:[],records:[]});groups.get(k).keys.push(key);groups.get(k).records.push(...rs)}
let works=[...groups].map(([id,g])=>{const rs=[...new Map(g.records.map((r,i)=>[String(r.id||'')||'file:'+r.nome+':'+i,r])).values()];const verified=rs.filter(r=>r.obra_verificada);const first=verified[0]||rs[0];const countries=[...new Set(rs.map(country).filter(x=>!pending(x)))];const c=countries.length>1?'Conflito':countries[0]||rs.map(country).find(value=>value&&!['Pendente','INDEFINIDO'].includes(value))||'Pendente';const authors=[...new Set(rs.map(author).filter(Boolean))];const prot=[...new Set(rs.flatMap(r=>Array.isArray(r.protagonistas_obra)?r.protagonistas_obra:[]).filter(Boolean))];const aliases=[...new Set(rs.flatMap(r=>[r.obra_verificada,r.catalogo,r.titulo,r.nome].filter(Boolean)))];const entry={id,title:canonical(first),authors,protagonists:prot,country:c,aliases,records:sortFiles(rs),keys:g.keys,status:c==='Conflito'?'conflito':countries.length?'confirmada':'pendente'};const label=seriesDisplay(entry);if(label)entry.title=label;return entry});
works.sort((a,b)=>a.title.localeCompare(b.title,'pt-BR'));
let ofPage=0;const pageSize=20;window.ofPage=0;
function matching(){const q=norm($('of-search').value),c=$('of-country').value,s=$('of-status').value;return works.filter(g=>(!q||[g.title,...g.aliases,...g.authors,...g.protagonists,...g.records.map(r=>r.nome)].some(x=>norm(x).includes(q)))&&(!c||g.country===c)&&(!s||g.status===s))}
function ofRender(){ofPage=window.ofPage||0;const matches=matching();const pages=Math.max(1,Math.ceil(matches.length/pageSize));ofPage=Math.max(0,Math.min(ofPage,pages-1));window.ofPage=ofPage;const selected=matches.slice(ofPage*pageSize,(ofPage+1)*pageSize);$('of-body').innerHTML=selected.map((g,i)=>{const uid='of-detail-'+ofPage+'-'+i;return '<tr><td><strong>'+escape(g.title)+'</strong></td><td>'+escape(g.authors.join(' / ')||'Pendente')+'</td><td>'+escape(g.protagonists.join(' / ')||'—')+'</td><td><span class="of-badge '+(g.status==='pendente'?'of-pending':'')+'">'+escape(countryName(g.country))+'</span></td><td>'+g.records.length+'</td><td><button type="button" class="row-expander" aria-expanded="false" aria-controls="'+uid+'" onclick="ofToggle(this)">›</button></td></tr><tr id="'+uid+'" hidden><td colspan="6"><div class="of-detail"><div><b>IDs de obras:</b> '+escape(g.keys.join(', '))+'</div><div><b>Títulos alternativos:</b> '+escape([...new Set(g.aliases.filter(t=>!String(t).toLowerCase().endsWith(".epub")&&norm(t)!==norm(g.title)))].slice(0,12).join(' / ')||'—')+'</div>'+(g.status==='conflito'?'<div class="of-warning">Origens conflitantes: revisar antes de confirmar.</div>':'')+'<table><thead><tr><th>Volume</th><th>ID mensagem</th><th>Arquivo</th><th>Título identificado</th><th>Origem do registro</th></tr></thead><tbody>'+g.records.map(r=>'<tr><td>'+escape(volumeRow(r)?.number??'—')+'</td><td>'+escape(r.id)+'</td><td>'+escape(r.nome)+'</td><td>'+escape(canonical(r))+'</td><td>'+escape(countryName(country(r)||'Pendente'))+'</td></tr>').join('')+'</tbody></table></div></td></tr>'}).join('')||'<tr><td colspan="6">Nenhuma obra encontrada</td></tr>';
$('of-summary').textContent=works.length+' obras consolidadas · '+works.reduce((n,g)=>n+g.records.length,0)+' EPUBs únicos por ID · '+works.filter(g=>g.status==='pendente').length+' pendentes · '+works.filter(g=>g.status==='conflito').length+' conflitos';$('of-range').textContent=matches.length+' resultados · página '+(ofPage+1)+' de '+pages;$('of-prev').disabled=ofPage===0;$('of-next').disabled=ofPage>=pages-1}
function ofToggle(button){const row=$(button.getAttribute('aria-controls'));row.hidden=!row.hidden;button.setAttribute('aria-expanded',String(!row.hidden))}
function ofExport(){const headers=['obra_id','obra','autor','protagonistas','origem','status','epub_id','arquivo','obra_origem'];const data=[headers,...matching().flatMap(g=>g.records.map(r=>[g.id,g.title,g.authors.join(' / '),g.protagonists.join(' / '),countryName(g.country),g.status,r.id||'',r.nome||'',r.obra_chave||'']))];const csv='\ufeff'+data.map(row=>row.map(v=>'"'+String(v??'').replace(/"/g,'""')+'"').join(';')).join('\r\n');const u=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download='check_epub_oficial.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
window.ofRender=ofRender;window.ofToggle=ofToggle;window.ofExport=ofExport;
const countries=[...new Set(works.map(g=>g.country))].sort((a,b)=>a.localeCompare(b,'pt-BR'));$('of-country').insertAdjacentHTML('beforeend',countries.map(c=>'<option value="'+escape(c)+'">'+escape(countryName(c))+'</option>').join(''));
ofRender();
})();
</script>'''

def inject(content, decisions):
    content = re.sub(r'<!-- CE_OFICIAL_SECTION_START -->.*?<!-- CE_OFICIAL_SECTION_END -->\s*', '', content, flags=re.S)
    # Idempotent and forward compatible with both original and CE-enhanced report.
    content = re.sub(r'\s*' + re.escape(START) + r'.*?' + re.escape(END) + r'\s*', '', content, flags=re.S)
    content = re.sub(r'\s*(?:' + re.escape(NAV) + r')?<button[^>]*id="nav-oficial".*?</button>\s*', '', content, flags=re.S)
    content = content.replace(NAV, '')
    anchor = '</nav>'
    if 'id="primaryTabs"' not in content or anchor not in content or 'const DATA=' not in content:
        raise ValueError('HTML do Check Epub não reconhecido; nenhum arquivo alterado')
    # Remove any previous Oficial tab but keep the section and its data available
    # in the generated HTML for future use.
    # A secao deve estar DENTRO do container <main class="main">.
    # Fora dele, quebra o fluxo e aparece longe do menu.
    content = content.replace('</main>', '<!-- CE_OFICIAL_SECTION_START -->' + SECTION + '<!-- CE_OFICIAL_SECTION_END -->\n</main>', 1)
    block = START + CSS + JS.replace('__DECISIONS__', json.dumps(decisions, ensure_ascii=False).replace('<','\\u003c')) + END
    content = content.replace('</body>',block+'\n</body>',1)
    return content

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--projeto',type=Path,default=Path.cwd())
    p.add_argument('--html',type=Path)
    args=p.parse_args(argv)
    project=args.projeto.expanduser().resolve()
    if (project/'RELATORIO_HTML_PROTEGIDO.md').exists():
        p.error('Relatório protegido: atualização interrompida para preservar as correções atuais.')
    path=args.html or project/'output'/'relatorio_telegram.html'
    if not path.exists():p.error(f'HTML não encontrado: {path}')
    dp=project/'output'/'oficial_decisions.json'
    decisions=json.loads(dp.read_text(encoding='utf-8')) if dp.exists() else {'merges':[]}
    if not isinstance(decisions,dict) or not isinstance(decisions.get('merges'),list):p.error('Formato inválido de oficial_decisions.json')
    source=path.read_text(encoding='utf-8')
    changed=inject(source,decisions)
    # Atomic write, no temporary backup of huge HTML unless requested by user.
    tmp=path.with_name(path.name+'.oficial_tmp')
    tmp.write_text(changed,encoding='utf-8');tmp.replace(path)
    print('Oficial instalada:',path,'| merges aprovados:',len(decisions['merges']))
if __name__=='__main__':main()

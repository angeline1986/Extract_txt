#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"

def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        header = f.readline()
        f.seek(0)
        sep = ";" if header.count(";") > header.count(",") else ","
        return list(csv.DictReader(f, delimiter=sep))

def status_of(row):
    s = row.get("status_verificacao", "").strip().lower()
    if "revis" in s or "aproxim" in s:
        return "revisar"
    if "nao_encontr" in s or "não_encontr" in s:
        return "nao_encontrado"
    if "exata" in s or "exact" in s:
        return "identificado"
    return "outro"

def main():
    files = sorted(OUTPUT.glob("*origens*ptbr.csv"))
    if not files:
        files = sorted(OUTPUT.glob("*origens*.csv"))
    if not files:
        raise SystemExit("CSV de classificação não encontrado em output/")

    source = files[-1]
    rows = read_csv(source)

    records = []
    for r in rows:
        records.append({
            "nome": r.get("nome_arquivo", ""),
            "titulo": r.get("titulo_normalizado", ""),
            "catalogo": r.get("titulo_catalogo", ""),
            "autor": r.get("autor_catalogo", ""),
            "idioma": r.get("idioma_original", ""),
            "pais": r.get("pais_origem", ""),
            "status": status_of(r),
            "status_original": r.get("status_verificacao", ""),
            "fonte": r.get("fonte_verificacao", ""),
            "id": r.get("id_mensagem", ""),
            "data": r.get("data_utc", ""),
            "link": r.get("link_mensagem", "")
        })

    statuses = Counter(r["status"] for r in records)
    languages = Counter(
        r["idioma"] or r["pais"]
        for r in records
        if r["status"] == "identificado"
        and (r["idioma"] or r["pais"])
    )

    inventory = {}
    originals = sorted((ROOT / "input").glob("telegram_midias_*.csv"))
    originals = [p for p in originals if "apenas_epub" not in p.name]
    if originals:
        media = read_csv(originals[-1])
        inventory["Total de mídias"] = len(media)
        inventory["EPUBs no inventário"] = sum(
            x.get("nome_arquivo", "").lower().endswith(".epub")
            for x in media
        )

    data = {
        "records": records,
        "statuses": dict(statuses),
        "languages": dict(languages),
        "inventory": inventory,
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "source": source.name
    }

    payload = json.dumps(data, ensure_ascii=False).replace(
        "<", "\\u003c"
    ).replace(">", "\\u003e").replace("&", "\\u0026")

    html = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Telegram · Check Epub</title>
<style>
:root {
  font-family: Inter,-apple-system,BlinkMacSystemFont,
    "Segoe UI",sans-serif;
  color:#17243a;
  background:#f6f8fc;
}
*{box-sizing:border-box}
body{margin:0}
button,input,select{font:inherit}
button{cursor:pointer}
.app{display:flex;min-height:100vh}
.sidebar{
  width:250px;flex-shrink:0;background:white;
  border-right:1px solid #e4eaf2;
  padding:24px 14px;
  position:sticky;top:0;height:100vh;
  transition:width .2s ease;
  overflow:hidden;
}
.sidehead{
  display:flex;align-items:center;
  justify-content:space-between;gap:8px;
  margin-bottom:32px;
}
.brand{
  display:flex;align-items:center;gap:9px;
  font-weight:750;white-space:nowrap;
  overflow:hidden;
}
.logo{
  background:#345fe8;color:white;
  border-radius:10px;padding:10px;
}
.toggle{
  width:34px;height:34px;flex-shrink:0;
  border:1px solid #dfe6f0;border-radius:9px;
  background:white;color:#53657d;
  font-size:22px;
}
.toggle:hover{background:#edf2ff}
.nav{
  display:flex;align-items:center;gap:12px;
  width:100%;border:0;background:transparent;
  padding:14px 12px;margin:4px 0;
  border-radius:9px;color:#64748b;
  text-align:left;white-space:nowrap;
}
.nav.active{
  background:#edf2ff;color:#3159cf;font-weight:700;
}
.navicon{font-size:20px;min-width:22px;text-align:center}
.navlabel{overflow:hidden}
.collapsed .sidebar{width:72px;padding:20px 10px}
.collapsed .sidehead{flex-direction:column;gap:15px}
.collapsed .brandname,.collapsed .navlabel{display:none}
.collapsed .nav{justify-content:center;padding:14px 0}
.collapsed .toggle{transform:rotate(180deg)}
.main{flex:1;min-width:0;padding:38px clamp(18px,4vw,60px)}
.eyebrow{
  color:#6378a0;font-size:12px;
  font-weight:750;letter-spacing:1.5px;
  text-transform:uppercase;
}
h1{font-size:30px;letter-spacing:-1px;margin:9px 0}
.sub{color:#78869b;margin:0 0 28px}
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
  gap:15px;
}
.card,.panel{
  background:white;border:1px solid #e7ebf2;
  border-radius:14px;
  box-shadow:0 2px 9px rgba(25,50,90,.025);
}
.card{padding:22px}
.label{color:#718097;font-size:13px}
.number{
  font-size:30px;font-weight:760;
  margin-top:12px;letter-spacing:-1px;
}
.panel{padding:24px;margin-top:20px}
.panel h2{font-size:17px;margin:0 0 20px}
.two{
  display:grid;grid-template-columns:1fr 1fr;
  gap:20px;
}
.bar{
  height:14px;border-radius:20px;
  background:#e7edf5;display:flex;overflow:hidden;
}
.legend{
  display:flex;gap:18px;flex-wrap:wrap;
  margin-top:18px;color:#68768a;font-size:13px;
}
.dot{
  display:inline-block;width:9px;height:9px;
  border-radius:50%;margin-right:5px;
}
.stat{
  display:flex;justify-content:space-between;
  gap:12px;padding:12px 0;
  border-bottom:1px solid #eef1f5;
}
.stat:last-child{border:0}
.muted{color:#77869b}
.notice{
  padding:15px;background:#f8faff;
  border:1px solid #e6ecfb;border-radius:9px;
  color:#5b6c89;line-height:1.6;
}
.toolbar{
  display:flex;gap:10px;flex-wrap:wrap;
  margin-bottom:18px;
}
.toolbar input,.toolbar select{
  padding:11px 12px;border:1px solid #dfe5ee;
  border-radius:8px;background:white;color:#26364d;
}
.toolbar input{flex:1;min-width:200px}
.action,.pagination button{
  border:1px solid #dfe5ee;border-radius:8px;
  background:white;color:#3457a5;
  padding:10px 14px;
}
.tablewrap{overflow:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th{
  text-align:left;color:#7b879a;
  font-weight:650;background:#f9fbfe;
}
td,th{padding:14px 12px;border-bottom:1px solid #edf0f5}
td{max-width:380px;overflow-wrap:anywhere}
.pill{
  display:inline-block;padding:5px 9px;
  border-radius:20px;font-size:11px;
  white-space:nowrap;
}
.identificado{background:#e5f7ee;color:#16855a}
.revisar{background:#fff3dc;color:#a66a09}
.nao_encontrado,.outro{background:#edf0f5;color:#69788d}
.pagination{
  display:flex;justify-content:space-between;
  align-items:center;gap:10px;
  padding-top:18px;color:#7a8799;font-size:13px;
}
.pagination button:disabled{opacity:.4}
.hidden{display:none!important}
@media(max-width:1000px){
  .grid{grid-template-columns:repeat(2,1fr)}
  .two{grid-template-columns:1fr}
}
@media(max-width:640px){
  .sidebar{width:72px;padding:14px 8px}
  .brandname,.navlabel{display:none}
  .sidehead{flex-direction:column}
  .nav{justify-content:center;padding:12px 0}
  .main{padding:24px 14px}
  .card{padding:14px}
  .number{font-size:24px}
}
</style>
</head>
<body>
<div class="app" id="app">
<aside class="sidebar">
  <div class="sidehead">
    <div class="brand">
      <span class="logo">▤</span>
      <span class="brandname">Check Epub</span>
    </div>
    <button class="toggle" id="toggle"
      onclick="toggleSidebar()"
      aria-label="Recolher menu"
      title="Recolher ou expandir menu">‹</button>
  </div>
  <button class="nav active" id="nav-overview"
    onclick="navigate('overview')" title="Visão geral">
    <span class="navicon">▦</span>
    <span class="navlabel">Visão geral</span>
  </button>
  <button class="nav" id="nav-explorer"
    onclick="navigate('explorer')" title="Explorador de EPUBs">
    <span class="navicon">▤</span>
    <span class="navlabel">Explorador de EPUBs</span>
  </button>
</aside>
<main class="main">
<section id="overview">
  <div class="eyebrow">Telegram / Dashboard</div>
  <h1>Visão geral</h1>
  <p class="sub" id="generated"></p>
  <div class="grid" id="cards"></div>
  <div class="panel">
    <h2>Qualidade da identificação</h2>
    <div class="bar" id="statusbar"></div>
    <div class="legend">
      <span><i class="dot" style="background:#27a477"></i>Identificados</span>
      <span><i class="dot" style="background:#e9ae46"></i>Para revisão</span>
      <span><i class="dot" style="background:#a7b3c4"></i>Não encontrados / outros</span>
    </div>
  </div>
  <div class="two">
    <div class="panel">
      <h2>Origens identificadas</h2>
      <div id="languages"></div>
    </div>
    <div class="panel">
      <h2>Inventário de mídias</h2>
      <div id="inventory"></div>
    </div>
  </div>
  <div class="panel">
    <h2>Nacionalidades das obras revisadas</h2>
    <p class="muted" id="verifiedOriginsSummary"></p>
    <div id="verifiedOrigins"></div>
  </div>
  <div class="panel">
    <h2>Cherrymist</h2>
    <div class="notice">
      Associação não verificada por catálogo.
      Não é possível confirmar obras da Cherrymist
      apenas pelo nome do arquivo.
    </div>
  </div>
</section>
<section id="explorer" class="hidden">
  <div class="eyebrow">Biblioteca / Pesquisa</div>
  <h1>Explorador de EPUBs</h1>
  <p class="sub">Pesquise e filtre as obras do inventário.</p>
  <div class="panel">
    <div class="toolbar">
      <input id="search"
        placeholder="Buscar título, arquivo ou autor"
        oninput="filterRecords()">
      <select id="status" onchange="filterRecords()">
        <option value="">Todos os status do catálogo</option>
        <option value="identificado">Identificados</option>
        <option value="revisar">Para revisão</option>
        <option value="nao_encontrado">Não encontrados</option>
        <option value="outro">Outros</option>
      </select>
      <select id="nationality" onchange="filterRecords()">
        <option value="">Todas as nacionalidades originais verificadas</option>
      </select>
      <button class="action" onclick="exportCSV()">
        Exportar CSV filtrado
      </button>
    </div>
    <div class="tablewrap">
      <table>
        <thead><tr>
          <th>Arquivo / obra</th><th>Autor</th>
          <th>Nacionalidade da obra</th><th>Protagonistas</th>
          <th>Verificadas</th><th>Encontrada em</th>
          <th>Status no catálogo</th><th>ID</th><th>Referência</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
    <div class="pagination">
      <span id="pageInfo"></span>
      <div>
        <button id="prev" onclick="changePage(-1)">Anterior</button>
        <button id="next" onclick="changePage(1)">Próximo</button>
      </div>
    </div>
  </div>
</section>
</main>
</div>
<script>
/*__DATA__*/
const $=id=>document.getElementById(id);
const fmt=n=>Number(n||0).toLocaleString('pt-BR');
const esc=s=>String(s??'').replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;',
  '"':'&quot;',"'":'&#39;'}[c]));
let filtered=DATA.records.slice(),page=0;
const pageSize=50;
const labels={
  identificado:'Identificado',revisar:'Revisar',
  nao_encontrado:'Não encontrado',outro:'Outro'
};

function toggleSidebar(){
  const collapsed=$('app').classList.toggle('collapsed');
  $('toggle').setAttribute('aria-expanded',String(!collapsed));
  try{
    localStorage.setItem('telegram-sidebar-collapsed',String(collapsed));
  }catch(e){}
}
try{
  if(localStorage.getItem('telegram-sidebar-collapsed')==='true')
    $('app').classList.add('collapsed');
}catch(e){}

function navigate(view){
  for(const name of ['overview','explorer']){
    $(name).classList.toggle('hidden',name!==view);
    $('nav-'+name).classList.toggle('active',name===view);
  }
  location.hash=view;
}
function metric(label,value){
  return '<div class="card"><div class="label">'+esc(label)+
    '</div><div class="number">'+fmt(value)+'</div></div>';
}
function stat(label,value){
  return '<div class="stat"><span class="muted">'+esc(label)+
    '</span><strong>'+fmt(value)+'</strong></div>';
}
$('generated').textContent='Atualizado em '+DATA.generated+
  ' · Fonte: '+DATA.source;
const counts=DATA.statuses;
const total=DATA.records.length;
$('cards').innerHTML=
  metric('EPUBs analisados',total)+
  metric('Identificados',counts.identificado)+
  metric('Para revisão',counts.revisar)+
  metric('Não encontrados',counts.nao_encontrado)+
  metric('Obras com nacionalidade confirmada',DATA.obra_origins?.work_count||0);
$('statusbar').innerHTML=
  '<span style="width:'+(100*(counts.identificado||0)/(total||1))+
  '%;background:#27a477"></span>'+
  '<span style="width:'+(100*(counts.revisar||0)/(total||1))+
  '%;background:#e9ae46"></span>'+
  '<span style="flex:1;background:#a7b3c4"></span>';
$('languages').innerHTML=
  Object.entries(DATA.languages).sort((a,b)=>b[1]-a[1])
  .map(([k,v])=>stat(k,v)).join('')||
  '<p class="muted">Nenhuma origem confirmada.</p>';
$('inventory').innerHTML=
  Object.entries(DATA.inventory).map(([k,v])=>stat(k,v)).join('')||
  '<p class="muted">Inventário não localizado.</p>';
const obraOrigins=DATA.obra_origins||{work_count:0,epub_count:0,countries:{}};
$('verifiedOriginsSummary').textContent=
  fmt(obraOrigins.work_count)+' obras · '+fmt(obraOrigins.epub_count)+
  ' EPUBs associados';
$('verifiedOrigins').innerHTML=
  Object.entries(obraOrigins.countries).sort((a,b)=>b[1]-a[1])
  .map(([k,v])=>stat(k,v)).join('')||
  '<p class="muted">Nenhuma nacionalidade revisada.</p>';
const nationalities=Object.entries(DATA.obra_origins?.countries||{})
  .sort((a,b)=>a[0].localeCompare(b[0],'pt-BR'));
$('nationality').innerHTML+=nationalities.map(([country,count])=>
  '<option value="'+esc(country)+'">'+esc(country)+' ('+fmt(count)+' obras)</option>').join('');

function filterRecords(){
  const q=$('search').value.trim().toLocaleLowerCase();
  const s=$('status').value,n=$('nationality').value;
  filtered=DATA.records.filter(r=>
    (!q||[r.nome,r.titulo,r.autor,r.catalogo,r.obra_verificada,
      r.autor_obra,r.nacionalidade_obra,r.localizada_em,
      (r.protagonistas_obra||[]).join(' ')]
      .some(v=>String(v).toLocaleLowerCase().includes(q)))&&
    (!s||r.status===s)&&
    (!n||r.nacionalidade_obra===n)
  );
  page=0;render();
}
function render(){
  const start=page*pageSize;
  const rows=filtered.slice(start,start+pageSize);
  $('tbody').innerHTML=rows.map(r=>
    '<tr><td><strong>'+esc(r.obra_verificada||r.nome)+'</strong>'+
    (r.obra_verificada&&r.nome?'<div class="muted">'+esc(r.nome)+'</div>':'')+
    (r.catalogo?'<div class="muted">'+esc(r.catalogo)+'</div>':'')+
    '</td><td>'+esc(r.autor_obra||r.autor||'—')+
    '</td><td>'+esc(r.nacionalidade_obra||'—')+
    '</td><td>'+esc((r.protagonistas_obra||[]).join(' / ')||'—')+
    '</td><td>'+esc(formatVerification(r.verificadas))+
    '</td><td>'+esc(r.localizada_em||'Não encontrada no catálogo')+
    '</td><td><span class="pill '+r.status+'">'+
    labels[r.status]+'</span></td><td>'+esc(r.id)+'</td><td>'+
    (r.referencia_obra?'<a href="'+esc(r.referencia_obra)+
      '" target="_blank" rel="noopener noreferrer">Abrir</a>':'—')+
    '</td></tr>'
  ).join('')||'<tr><td colspan="9">Nenhum resultado</td></tr>';
  $('pageInfo').textContent=fmt(filtered.length)+
    ' resultados · página '+(page+1)+' de '+
    Math.max(1,Math.ceil(filtered.length/pageSize));
  $('prev').disabled=page===0;
  $('next').disabled=(page+1)*pageSize>=filtered.length;
}
function changePage(delta){page+=delta;render()}
function formatVerification(value){
  if(!value)return 'Pendente';
  const m=String(value).match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}):(\d{2}))?/);
  if(m)return m[3]+'/'+m[2]+'/'+m[1]+' '+(m[4]||'00')+':'+(m[5]||'00')+':'+(m[6]||'00');
  return String(value);
}
function exportCSV(){
  const cols=['nome','titulo','autor','idioma','pais',
    'obra_verificada','autor_obra','nacionalidade_obra','protagonistas_obra',
    'verificadas','localizada_em','referencia_obra','status','status_original','catalogo','fonte','id','data'];
  const quote=v=>'"'+String(Array.isArray(v)?v.join(' / '):(v??'')).replace(/"/g,'""')+'"';
  const csv='\ufeff'+[
    cols.join(';'),
    ...filtered.map(r=>cols.map(c=>quote(r[c])).join(';'))
  ].join('\r\n');
  const url=URL.createObjectURL(
    new Blob([csv],{type:'text/csv;charset=utf-8'})
  );
  const a=document.createElement('a');
  a.href=url;a.download='epubs_filtrados.csv';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
render();
navigate(location.hash==='#explorer'?'explorer':'overview');
</script>
</body></html>'''

    html = html.replace("/*__DATA__*/", "const DATA=" + payload + ";")
    destination = OUTPUT / "relatorio_telegram.html"
    destination.write_text(html, encoding="utf-8")
    # CHECK_EPUB_INTEGRACAO_V1
    import subprocess as _ce_subprocess, sys as _ce_sys
    if (ROOT / "output" / "check_epub_varredura.json").exists():
        _ce_subprocess.run([_ce_sys.executable, str(ROOT / "scripts" / "check_epub_consolidar.py"),
                           "--projeto", str(ROOT), "--somente-html"], check=True)

    print("HTML:", destination)
    print("EPUBs:", len(records))
    print("Identificados:", statuses["identificado"])
    print("Para revisão:", statuses["revisar"])
    print("Não encontrados:", statuses["nao_encontrado"])
    print("Outros:", statuses["outro"])

if __name__ == "__main__":
    main()

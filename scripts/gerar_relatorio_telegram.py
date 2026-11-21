#!/usr/bin/env python3
import csv
import ast
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"

COUNTRY_CODES = {
    "CN": "China",
    "KR": "Coreia do Sul",
    "JP": "Japão",
}

THAI_TITLE_CORRECTIONS = {
    "84060": ("Heartbound", "obra_01926"),
    "83243": ("Heartbound", "obra_01926"),
    "75911": ("Crazy Love Moo Moo", "obra_01567"),
    "66740": ("NITI man, society and lover", "obra_01255"),
    "58718": ("NITI man, society and lover", "obra_01255"),
    "5850": ("Cutie Pie", "obra_01055"),
    "5857": ("Cutie Pie", "obra_01055"),
    "55509": ("Space: The Gap Between Us", "obra_00997"),
    "1965": ("My Only 12%", "obra_00093"),
    "1568": ("My Only 12%", "obra_00093"),
}

KOREAN_LOOK_AT_ME_IDS = {"59957", "59943", "59940", "59867", "59865"}

def catalog_author(value):
    value = str(value or "").strip()
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        parsed = value
    if isinstance(parsed, (list, tuple)):
        return " / ".join(str(item).strip() for item in parsed if str(item).strip())
    return str(parsed or "").strip()

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
    if (ROOT / "RELATORIO_HTML_PROTEGIDO.md").exists():
        raise SystemExit("Relatório protegido: geração interrompida para preservar as correções atuais.")
    files = sorted(OUTPUT.glob("*origens*ptbr.csv"))
    if not files:
        files = sorted(OUTPUT.glob("*origens*.csv"))
    if not files:
        raise SystemExit("CSV de classificação não encontrado em output/")

    source = files[-1]
    all_rows = read_csv(source)
    local_manifest = ROOT / "input/epubs_locais_confirmados_20261118.json"
    if not local_manifest.exists():
        raise SystemExit("Manifesto de EPUBs locais ausente; confira a disponibilidade antes de gerar o painel.")
    local_epub_ids = json.loads(local_manifest.read_text(encoding="utf-8"))["ids"]
    if len(local_epub_ids) != len(set(local_epub_ids)):
        raise SystemExit("Manifesto de EPUBs locais contém IDs duplicados.")
    catalog_ids = {r.get("id_mensagem", "") for r in all_rows}
    if not set(local_epub_ids) <= catalog_ids:
        raise SystemExit("Manifesto de EPUBs locais contém IDs ausentes do inventário.")
    local_id_set = set(local_epub_ids)
    rows = [r for r in all_rows if r.get("id_mensagem", "") in local_id_set]
    if len(rows) != len(local_id_set):
        raise SystemExit("A contagem do inventário local não corresponde ao manifesto.")

    records = []
    for r in rows:
        records.append({
            "nome": r.get("nome_arquivo", ""),
            "titulo": r.get("titulo_normalizado", ""),
            "catalogo": r.get("titulo_catalogo", ""),
            "autor": catalog_author(r.get("autor_catalogo", "")),
            "idioma": r.get("idioma_original", ""),
            "pais": r.get("pais_origem", ""),
            "nacionalidade_obra": COUNTRY_CODES.get(
                r.get("pais_origem", "").strip().upper(),
                "Pendente" if r.get("pais_origem", "").strip().upper() == "INDEFINIDO"
                else r.get("pais_origem", "").strip(),
            ),
            "fonte_nacionalidade_obra": r.get("fonte_verificacao", ""),
            "referencia_obra": r.get("fonte_verificacao", ""),
            "status_catalogo": r.get("status_verificacao", ""),
            "evidencia_catalogo": r.get("evidencia", ""),
            "id": r.get("id_mensagem", ""),
            "data": r.get("data_utc", ""),
            "link": r.get("link_mensagem", "")
        })
        if r.get("id_mensagem") in {"83728", "83730"}:
            records[-1].update({
                "titulo": "Even Better",
                "obra_verificada": "Even Better",
                "autor_obra": "Peachhplease",
                "nacionalidade_obra": "Tailândia",
                "protagonistas_obra": ["Jettana Khieo (Jamie)", "Marvis Lee (Mars)"],
            })
        thai_correction = THAI_TITLE_CORRECTIONS.get(r.get("id_mensagem"))
        if thai_correction:
            title, work_key = thai_correction
            records[-1].update({
                "titulo": title,
                "obra_verificada": title,
                "obra_chave": work_key,
                "nacionalidade_obra": "Tailândia",
            })
        if r.get("id_mensagem") == "75106":
            records[-1].update({
                "obra_verificada": "Why Do All My Roommates Look at Me Like This?",
                "obra_chave": "obra_02841",
                "autor_obra": "Gong Zi Yu Ge (公子于歌)",
                "nacionalidade_obra": "China",
                "protagonistas_obra": ["Sui Yi", "Jiang Chengyao", "Gu Qingyang", "Ling Xuezhu"],
            })
        elif r.get("id_mensagem") in KOREAN_LOOK_AT_ME_IDS:
            records[-1].update({
                "obra_verificada": "Look at Me",
                "obra_chave": "obra_01113",
                "autor_obra": "Tansan",
                "nacionalidade_obra": "Coreia do Sul",
                "protagonistas_obra": ["Heerak Cho", "Yoon Doseon (Dooseon)"],
            })

    statuses = Counter(status_of(r) for r in rows)
    languages = Counter(
        r.get("idioma_original", "") or r.get("pais_origem", "")
        for r in rows
        if status_of(r) == "identificado"
        and (r.get("idioma_original", "") or r.get("pais_origem", ""))
    )

    data = {
        "records": records,
        "languages": dict(languages),
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
html{scrollbar-width:none;-ms-overflow-style:none}
html::-webkit-scrollbar{display:none}
body{margin:0}
button,input,select{font:inherit}
button{cursor:pointer}
.app{display:block;min-height:100vh}
.primary-tabs{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 0 12px;padding:0;border-bottom:1px solid #e8edf3;overflow:visible}
.nav{display:flex;align-items:center;gap:8px;flex:none;border:0;border-bottom:2px solid transparent;background:transparent;padding:12px 14px;margin:0 0 -1px;border-radius:8px 8px 0 0;color:#64748b;text-align:center;white-space:nowrap}
.primary-tabs .navicon{display:none}
.nav.active{
  background:#edf2ff;border-bottom-color:#345fe8;color:#3159cf;font-weight:700;
}
.navlabel{overflow:hidden}
.main{min-width:0;max-width:1500px;margin:0 auto;padding:30px clamp(18px,4vw,60px)}
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
.panel{padding:16px;margin-top:12px}
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
  border-bottom:1px solid #e8edf3;
}
.stat:last-child{border:0}
.donut-layout{display:grid;grid-template-columns:minmax(240px,1fr) minmax(260px,1fr);align-items:center;gap:26px;padding:8px 12px 4px}
.donut-viz{position:relative;width:min(100%,420px);margin:auto;aspect-ratio:1}
.donut-viz svg{display:block;width:100%;height:100%;overflow:visible}
.donut-segment{fill:none;stroke-width:32;transition:stroke-width .14s ease,opacity .14s ease;cursor:pointer}
.donut-segment:hover,.donut-segment:focus{stroke-width:38;opacity:.9;outline:none}
.donut-center{position:absolute;inset:50% auto auto 50%;transform:translate(-50%,-50%);text-align:center;pointer-events:none}
.donut-center strong{display:block;font-size:34px;letter-spacing:-1px}
.donut-center span{display:block;color:#718097;font-size:14px}
.donut-legend{display:grid;gap:4px}
.donut-legend-item{display:grid;grid-template-columns:12px minmax(90px,1fr) auto;align-items:center;gap:10px;padding:9px 0;color:#26364d}
.donut-swatch{width:11px;height:11px;border-radius:4px}
.donut-legend-count{text-align:right;white-space:nowrap;font-size:13px;font-weight:650}
.donut-legend-count span{display:block;color:#718097;font-weight:450;font-size:12px}
.donut-tooltip{position:fixed;z-index:100;display:none;max-width:250px;padding:10px 12px;border-radius:8px;background:#17243a;color:white;box-shadow:0 8px 24px #17243a30;font-size:13px;line-height:1.45;pointer-events:none}
.donut-tooltip strong{font-size:14px}
.muted{color:#77869b}
.notice{
  padding:15px;background:#f8fafc;
  border:1px solid #e6ecfb;border-radius:9px;
  color:#5b6c89;line-height:1.6;
}
.cherrymist-table{min-width:820px}
.cherrymist-table th{text-align:center}
.cherrymist-table td{vertical-align:top}
.cherrymist-table a{color:#3457a5}
.cherrymist-file{display:block;white-space:nowrap}
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
td,th{padding:14px 12px;border-bottom:1px solid #e8edf3}
td{max-width:380px;overflow-wrap:anywhere}
.explorer-title{display:flex;align-items:center;gap:8px;min-width:0}
.explorer-table{table-layout:fixed}
.explorer-table th:nth-child(1){width:25%}.explorer-table th:nth-child(2){width:16%}.explorer-table th:nth-child(3){width:13%}.explorer-table th:nth-child(4){width:25%}.explorer-table th:nth-child(5){width:12%}.explorer-table th:nth-child(6){width:5%}.explorer-table th:nth-child(7){width:4%}
.row-expander{display:grid;place-items:center;flex:0 0 22px;width:22px;height:22px;margin:0;padding:0;border:1px solid #e8edf3;border-radius:6px;background:#fff;color:#718096;cursor:pointer}
.row-expander:hover,.row-expander[aria-expanded="true"]{background:#f1f5f9;color:#334155;border-color:#cbd5e1}
.row-expander .chevron{font-size:16px;line-height:1;transition:transform .15s ease}
.row-expander[aria-expanded="true"] .chevron{transform:rotate(90deg)}
.explorer-book{min-width:0}
.explorer-expand-cell{text-align:right;width:1%;white-space:nowrap}
.explorer-expand-cell .row-expander{margin-left:auto}
.novel-browser{display:grid;grid-template-columns:260px minmax(0,1fr);gap:18px;align-items:start}
.novel-facets{position:sticky;top:18px;padding:18px;background:#fff;border:1px solid #e7ebf2;border-radius:12px}
.novel-facet-heading{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px}
.novel-facet-heading strong{font-size:14px}
.novel-clear{padding:5px 7px;border:0;background:transparent;color:#3457a5;font-size:12px}
.novel-facet-tabs{display:grid;grid-template-columns:1fr 1fr;gap:3px;padding:3px;margin-bottom:12px;border-radius:9px;background:#eff3f9}
.novel-facet-tab{min-height:32px;padding:6px 10px;border:0;border-radius:7px;background:transparent;color:#64748b;font-size:12px;font-weight:600}
.novel-facet-tab[aria-pressed="true"]{background:#fff;color:#24324a;box-shadow:0 1px 4px #17243a20}
.novel-facet-search{box-sizing:border-box;width:100%;padding:8px 9px;margin-bottom:10px;border:1px solid #dfe5ee;border-radius:7px;font-size:12px}
.novel-facet-list{display:grid;gap:2px;max-height:min(68vh,760px);overflow-y:auto;overflow-x:hidden}
.novel-facet-option{display:grid;grid-template-columns:14px minmax(0,1fr) max-content;align-items:center;gap:9px;padding:7px 6px;border-radius:6px;color:#334155;font-size:13px;cursor:pointer}
.novel-facet-option:hover{background:#f5f7fb}
.novel-facet-option input{width:14px;height:14px;margin:0;accent-color:#345fe8}
.novel-facet-option>span:first-of-type{min-width:0;overflow-wrap:anywhere}
.novel-facet-count{min-width:2ch;color:#718097;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.novel-results{min-width:0;padding:18px;background:#fff;border:1px solid #e7ebf2;border-radius:12px;box-shadow:0 2px 9px rgba(25,50,90,.025)}
.novel-toolbar{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:16px}
.novel-toolbar-left,.novel-toolbar-right{display:flex;align-items:center;gap:10px;min-width:0}
.novel-search{box-sizing:border-box;width:185px;max-width:20vw;padding:9px 11px;border:1px solid #dfe5ee;border-radius:8px}
.novel-custom-select{position:relative;flex:0 1 175px;min-width:145px}
.novel-custom-trigger{box-sizing:border-box;width:100%;min-height:38px;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;border:1px solid #dfe5ee;border-radius:8px;background:#fff;color:#334155;text-align:left;cursor:pointer}
.novel-custom-trigger:hover,.novel-custom-trigger[aria-expanded="true"]{border-color:#9bb0de}
.novel-custom-trigger-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.novel-custom-menu{box-sizing:border-box;position:absolute;z-index:35;top:calc(100% + 5px);left:0;width:min(340px,calc(100vw - 24px));max-width:calc(100vw - 24px);padding:8px;border:1px solid #dfe5ee;border-radius:9px;background:#fff;box-shadow:0 10px 28px #172b4d20;overflow-x:hidden}
.novel-custom-menu[hidden]{display:none}
.novel-custom-search{box-sizing:border-box;width:100%;padding:8px 9px;margin-bottom:6px;border:1px solid #dfe5ee;border-radius:6px}
.novel-custom-options{box-sizing:border-box;width:100%;max-width:100%;max-height:260px;overflow-y:auto;overflow-x:hidden}
.novel-custom-option{box-sizing:border-box;width:100%;min-width:0;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 9px;border:0;border-radius:6px;background:#fff;color:#334155;text-align:left;cursor:pointer;overflow:hidden}
.novel-custom-option span:first-child{min-width:0;white-space:normal;overflow-wrap:anywhere}
.novel-custom-option:hover,.novel-custom-option[aria-selected="true"]{background:#f0f4fb}
.novel-custom-option-count{flex:none;color:#718097;white-space:nowrap}
.novel-segmented{display:inline-flex;padding:3px;border:1px solid #dfe5ee;border-radius:8px;background:#f7f9fc;white-space:nowrap}
.novel-segmented button{padding:6px 10px;border:0;border-radius:6px;background:transparent;color:#64748b;font-size:12px}
.novel-segmented button[aria-pressed="true"]{background:#fff;color:#3457a5;box-shadow:0 1px 4px #17243a20}
.novel-filter-count{color:#64748b;font-size:12px;white-space:nowrap}
.novel-export{padding:8px 11px;border:1px solid #dfe5ee;border-radius:8px;background:#fff;color:#3457a5;white-space:nowrap}
.novel-summary-table{table-layout:fixed}.novel-summary-table th:nth-child(1){width:31%}.novel-summary-table th:nth-child(2){width:16%;text-align:center}.novel-summary-table th:nth-child(3){width:23%;text-align:center}.novel-summary-table th:nth-child(4){width:14%;text-align:center}.novel-summary-table th:nth-child(5){width:11%;text-align:center}.novel-summary-table th:nth-child(6){width:5%}
.novel-summary-table th{color:#3159cf;text-align:center}
.novel-summary-table td:nth-child(4),.novel-summary-table td:nth-child(5){text-align:center}
.novel-summary-table td:nth-child(2),.novel-summary-table td:nth-child(3){text-align:center}
.novel-summary-table td:nth-child(6){text-align:right;padding-right:16px}
.novel-summary-row{cursor:pointer}.novel-summary-row:hover{background:#f8faff}
.novel-summary-title{display:flex;align-items:center;gap:10px;min-width:0;font-weight:650;color:#24324a}
.novel-summary-expand{display:inline-grid;place-items:center;width:30px;height:30px;border:1px solid #e5eaf1;border-radius:8px;background:#fff;color:#718097;font-size:23px;line-height:1;transition:transform .15s ease,background .15s ease,color .15s ease}
.novel-summary-row:hover .novel-summary-expand{background:#edf2ff;color:#3457a5}
.novel-summary-row[aria-expanded="true"] .novel-summary-expand{transform:rotate(90deg);background:#edf2ff;color:#3457a5}
.novel-count-badge,.novel-country-badge{display:inline-flex;align-items:center;justify-content:center;padding:4px 9px;border-radius:999px;background:#f0f3f8;color:#53657d;font-size:12px;font-weight:650;white-space:nowrap}
.novel-country-badge{white-space:normal;text-align:center;overflow-wrap:anywhere;max-width:100%}
.novel-count-badge.multiple{background:#eaf0ff;color:#3457a5}
.novel-country-badge.pending{background:#fff3dc;color:#a66a09}
.novel-summary-detail[hidden]{display:none!important}
.novel-summary-detail td{max-width:none;padding:0!important;background:#f8fafc}
.novel-files{padding:14px 18px 16px 42px;border-top:1px solid #e8edf3;background:#f8fafc}
.novel-work-facts{margin:0 0 12px;border:1px solid #e5eaf1;border-radius:8px;background:#fff;overflow:hidden}
.novel-work-fact{display:grid;grid-template-columns:minmax(120px,180px) minmax(0,1fr);gap:16px;padding:9px 12px;border-bottom:1px solid #e8edf3;line-height:1.5}
.novel-work-fact:last-child{border-bottom:0}
.novel-work-fact strong{color:#334155}
.novel-file-list{display:grid;gap:8px}
.novel-file-item{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:10px 13px;border:1px solid #e5eaf1;border-radius:9px;background:#fff;color:#24324a}
.novel-file-name{display:flex;align-items:center;gap:9px;min-width:0;overflow-wrap:anywhere}
.novel-file-icon{flex:none;color:#718097;font-size:14px}
.novel-file-id{flex:none;color:#718097;font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap}
.novel-summary-footer{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;padding-top:14px;color:#64748b;font-size:14px}
.novel-summary-footer-left{display:flex;align-items:center;justify-self:start}
.novel-page-size{padding:7px 28px 7px 9px;border:1px solid #dfe5ee;border-radius:7px;background:#fff;color:#64748b;font-size:14px}
.novel-summary-range{justify-self:center;color:#64748b;font-size:14px;font-weight:400;font-variant-numeric:tabular-nums}
.novel-summary-pager{display:flex;align-items:center;justify-content:flex-end;justify-self:end;gap:12px}
.novel-summary-pager button{display:grid;place-items:center;width:42px;height:38px;padding:0;border:1px solid #dceef7;border-radius:9px;background:#fff;color:#64748b;font-size:14px;font-weight:400}
.novel-summary-pager span{min-width:42px;text-align:center;color:#64748b;font-size:14px;font-weight:400;font-variant-numeric:tabular-nums}
.novel-summary-pager button:disabled{opacity:.4;cursor:default}
.data-row td{vertical-align:middle}
.detail-row[hidden]{display:none!important}
.detail-row:not([hidden]){display:table-row}
.detail-row>td{max-width:none!important;padding:0!important;background:#f8fafc!important;border-bottom:1px solid #e8edf3}
.detail-content{box-sizing:border-box;display:block;width:100%;max-width:none;padding:14px 18px 16px 42px;background:#f8fafc;border-top:1px solid #e8edf3}
.detail-heading{display:flex;align-items:center;gap:8px;margin:0 0 8px;color:#52627a;font-size:12px;font-weight:650}
.detail-table-wrap{display:block;width:100%;overflow-x:auto}
.detail-table{box-sizing:border-box;width:100%;min-width:640px;table-layout:fixed;margin:0;font-size:12px;background:#fff;border:1px solid #e8edf3;border-radius:6px;overflow:hidden}
.detail-table th{background:#f8fafc;color:#718096;font-size:11px;font-weight:600}
.detail-table th:nth-child(1){width:38%}.detail-table th:nth-child(2){width:11%}.detail-table th:nth-child(3){width:15%}.detail-table th:nth-child(4){width:17%}.detail-table th:nth-child(5){width:19%}
.detail-table td,.detail-table th{max-width:none!important;padding:9px 11px;border-bottom:1px solid #e8edf3;vertical-align:top}
.detail-table td:first-child{font-weight:550;color:#334155}
.detail-table tbody tr:last-child td{border-bottom:0}
.detail-table a{color:#3457a5}
.pill{
  display:inline-block;padding:5px 9px;
  border-radius:20px;font-size:11px;
  white-space:nowrap;
}
.identificado{background:#e5f7ee;color:#16855a}
.revisar{background:#fff3dc;color:#a66a09}
.nao_encontrado,.outro{background:#e8edf3;color:#69788d}
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
  .donut-layout{grid-template-columns:1fr;gap:10px}
  .novel-browser{grid-template-columns:1fr}
  .novel-facets{position:static}
  .novel-facet-list{max-height:240px}
}
@media(max-width:1000px){.novel-toolbar{align-items:stretch;flex-direction:column}.novel-toolbar-left,.novel-toolbar-right{justify-content:space-between;flex-wrap:wrap}.novel-search{width:100%;max-width:none;flex:1}.novel-custom-select{flex:1 1 180px}}
@media(max-width:760px){.novel-summary-footer{grid-template-columns:1fr 1fr;row-gap:10px}.novel-summary-footer-left{grid-column:1;grid-row:1}.novel-summary-range{grid-column:1 / -1;grid-row:2}.novel-summary-pager{grid-column:2;grid-row:1;gap:10px}}
@media(max-width:640px){
  .primary-tabs{padding:0}
  .nav{padding:10px 11px;font-size:13px}
  .main{padding:24px 14px}
  .card{padding:14px}
  .number{font-size:24px}
}
@media(max-width:520px){.novel-work-fact{grid-template-columns:1fr;gap:2px}}
</style>
</head>
<body>
<div class="app" id="app">
<main class="main">
<nav class="primary-tabs" id="primaryTabs" aria-label="Navegação principal">
  <button class="nav active" id="nav-overview" onclick="navigate('overview')" title="Visão geral"><span class="navlabel">Visão geral</span></button>
  <button class="nav" id="nav-novels" onclick="navigate('novels')" title="EPUBs por novel"><span class="navlabel">EPUBs por novel</span></button>
</nav>
<section id="overview">
  <div id="overviewPanel" role="tabpanel" aria-labelledby="nav-overview">
  <div class="grid" id="cards"></div>
  <div class="panel">
    <h2>Origens das obras no acervo</h2>
    <p class="muted" id="verifiedOriginsSummary"></p>
    <div id="verifiedOrigins"></div>
    <div id="donutTooltip" class="donut-tooltip" role="status" aria-live="polite"></div>
  </div>
  <div class="panel">
    <h2>Cherrymist</h2>
    <p class="muted" id="cherrymistSummary"></p>
    <div class="tablewrap"><table class="cherrymist-table"><thead><tr><th>Obra no catálogo</th><th>Correspondência local</th><th>Autor</th><th>Origem</th><th>EPUB local / ID</th><th>Evidência no EPUB</th></tr></thead><tbody id="cherrymistBody"></tbody></table></div>
  </div>
  </div>
  <div id="novelsPanel" class="hidden" role="tabpanel" aria-labelledby="nav-novels">
  <div class="panel">
    <div class="novel-browser">
      <aside class="novel-facets">
        <div class="novel-facet-heading"><strong>Filtros</strong><button class="novel-clear" type="button" onclick="clearNovelFilters()">Limpar filtros</button></div>
        <div class="novel-facet-tabs" role="group" aria-label="Tipo de filtro">
          <button type="button" class="novel-facet-tab" id="novel-facet-country" aria-pressed="true" onclick="setNovelSidebarFacet('country')">Origem</button>
          <button type="button" class="novel-facet-tab" id="novel-facet-author" aria-pressed="false" onclick="setNovelSidebarFacet('author')">Autor</button>
        </div>
        <input id="novelFacetSearch" class="novel-facet-search" placeholder="Filtrar origem..." aria-label="Filtrar origem" oninput="renderNovelFacetFilters()">
        <div id="novelFacetFilters" class="novel-facet-list"></div>
      </aside>
      <div class="novel-results">
        <div class="novel-toolbar">
          <div class="novel-toolbar-left">
            <input id="novelSummarySearch" class="novel-search" placeholder="Buscar novel" oninput="novelSummaryPage=0;renderNovelSummary()">
            <div class="novel-custom-select" id="novel-author-filter"><button type="button" class="novel-custom-trigger" id="novel-author-button" aria-haspopup="listbox" aria-expanded="false" onclick="toggleNovelDropdown('author')"><span class="novel-custom-trigger-label" id="novel-author-label">Autores</span><span aria-hidden="true">⌄</span></button><div class="novel-custom-menu" id="novel-author-menu" hidden><input class="novel-custom-search" id="novel-author-search" placeholder="Buscar autor" aria-label="Buscar autor" oninput="renderNovelDropdown('author')"><div class="novel-custom-options" id="novel-author-options" role="listbox" aria-label="Autores"></div></div></div>
            <div class="novel-custom-select" id="novel-protagonist-filter"><button type="button" class="novel-custom-trigger" id="novel-protagonist-button" aria-haspopup="listbox" aria-expanded="false" onclick="toggleNovelDropdown('protagonist')"><span class="novel-custom-trigger-label" id="novel-protagonist-label">Protagonista</span><span aria-hidden="true">⌄</span></button><div class="novel-custom-menu" id="novel-protagonist-menu" hidden><input class="novel-custom-search" id="novel-protagonist-search" placeholder="Buscar protagonista" aria-label="Buscar protagonista" oninput="renderNovelDropdown('protagonist')"><div class="novel-custom-options" id="novel-protagonist-options" role="listbox" aria-label="Protagonistas"></div></div></div>
            <div class="novel-segmented" role="group" aria-label="Filtrar quantidade de EPUBs">
              <button type="button" data-epub-filter="all" aria-pressed="true" onclick="setNovelQuantityFilter('all')">Todos</button>
              <button type="button" data-epub-filter="one" aria-pressed="false" onclick="setNovelQuantityFilter('one')">1 EPUB</button>
              <button type="button" data-epub-filter="multi" aria-pressed="false" onclick="setNovelQuantityFilter('multi')">+1 EPUB</button>
            </div>
          </div>
          <div class="novel-toolbar-right"><button class="novel-export" type="button" onclick="exportNovelSummaryCSV()">Exportar CSV</button></div>
        </div>
        <div class="tablewrap"><table class="novel-summary-table"><thead><tr><th>Obra</th><th>Autor</th><th>Protagonistas</th><th>Origem</th><th>Qtd. EPUBs</th><th aria-label="Expandir"></th></tr></thead><tbody id="novelSummaryBody"></tbody></table></div>
        <div class="novel-summary-footer"><div class="novel-summary-footer-left"><select id="novelPageSize" class="novel-page-size" aria-label="Quantidade por página" onchange="setNovelPageSize(this.value)"><option>10</option><option>20</option><option>30</option><option>40</option><option>50</option><option>60</option></select></div><span id="novelSummaryRange" class="novel-summary-range"></span><div class="novel-summary-pager"><button type="button" id="novelSummaryPrev" aria-label="Página anterior" onclick="moveNovelSummary(-1)">&lt;&lt;</button><span id="novelSummaryPageLabel"></span><button type="button" id="novelSummaryNext" aria-label="Próxima página" onclick="moveNovelSummary(1)">&gt;&gt;</button></div></div>
      </div>
    </div>
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
      <select id="nationality" onchange="filterRecords()">
        <option value="">Origem</option>
        <option value="__nao_identificado__">Não identificado</option>
      </select>
      <button class="action" onclick="exportCSV()">
        Exportar CSV filtrado
      </button>
    </div>
    <div class="tablewrap">
      <table class="explorer-table">
        <thead><tr>
          <th>Novel</th><th>Autor</th>
          <th>Origem</th><th>Protagonistas</th>
          <th>Verificadas</th><th>EPUBs</th><th aria-label="Expandir"></th>
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
function groupNorm(value){return String(value||'').normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'').toLocaleLowerCase('pt-BR').replace(/[^a-z0-9]+/g,' ').trim()}
function countryNorm(value){return String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR').replace(/[^a-z0-9]+/g,' ').trim()}
function countryName(value){const key=countryNorm(value);if(key==='nao identificada obra original em ingles')return 'Internacional (OEL — inglês)';if(key==='nao identificada fanfic em ingles')return 'Fanfic (inglês)';if(key.startsWith('nao identificad'))return 'Não identificada';const names={china:'China',chinesa:'China','coreia do sul':'Coreia do Sul','sul coreana':'Coreia do Sul','estados unidos':'Estados Unidos',estadunidense:'Estados Unidos','united states':'Estados Unidos','united states of america':'Estados Unidos',tailandia:'Tailândia',tailandesa:'Tailândia',canada:'Canadá',canadense:'Canadá','reino unido':'Reino Unido',britanica:'Reino Unido',britanico:'Reino Unido',japan:'Japão',japanese:'Japão',japao:'Japão',japonesa:'Japão',italia:'Itália',italiana:'Itália',dinamarca:'Dinamarca',dinamarquesa:'Dinamarca',australia:'Austrália',australiana:'Austrália',filipina:'Filipinas',filipinas:'Filipinas',mexico:'México',mexicana:'México',russia:'Rússia',russa:'Rússia',irlanda:'Irlanda',irlandesa:'Irlanda',singapura:'Singapura',singapurense:'Singapura',suecia:'Suécia',sueca:'Suécia',espanha:'Espanha',espanhola:'Espanha',chile:'Chile',chilena:'Chile',taiwan:'Taiwan',taiwanesa:'Taiwan','nova zelandia':'Nova Zelândia','republica tcheca':'República Tcheca',india:'Índia'};return names[key]||String(value||'').trim()}
// IDs de EPUB sem obra_chave conferidos por autor e título no catálogo e no arquivo.
const chinaEpubWorkKeys=new Map([
  ['obra_02348',['92560']],['obra_02808',['90558','80091']],
  ['obra_02269',['90361','82106']],['obra_00802',['83315']],
  ['obra_02254',['78182']],['obra_01470',['77903']],
  ['obra_01914',['72755']],['obra_01385',['71825']],
  ['obra_02772',['60511']],['obra_02718',['59289']],
  ['obra_00034',['45853','17062','1933']],
  ['obra_03006',['19662','3269']],['obra_01423',['4302']]
].flatMap(([key,ids])=>ids.map(id=>[id,key])));
function novelAliasKey(record,name){
  const title=groupNorm(name);if(!title)return '';
  if(record.nacionalidade_obra!=='China')return title;
  const author=novelIdentityText(record.autor_obra||record.autor);
  return author?'china|'+author+'|'+title:'';
}
function makeNovelGroups(records){
  const aliases=new Map(),ambiguous=new Set();
  records.filter(r=>r.obra_chave).forEach(r=>[r.obra_verificada,r.titulo,r.catalogo].filter(Boolean).forEach(name=>{
    const alias=novelAliasKey(r,name);if(!alias)return;
    if(aliases.has(alias)&&aliases.get(alias)!==String(r.obra_chave))ambiguous.add(alias);else aliases.set(alias,String(r.obra_chave));
  }));
  const groups=new Map();
  records.forEach((r,index)=>{
    const title=r.obra_verificada||r.catalogo||r.titulo||r.nome||'Novel sem título';
    const alias=groupNorm(title),lookup=novelAliasKey(r,title);
    const mapped=lookup&&!ambiguous.has(lookup)?aliases.get(lookup):'';
    const reviewed=r.nacionalidade_obra==='China'?chinaEpubWorkKeys.get(String(r.id)):'';
    const workKey=r.obra_chave||reviewed||mapped;
    const key=workKey?'obra:'+workKey:'titulo:'+alias+'|autor:'+groupNorm(r.autor_obra||r.autor);
    let g=groups.get(key);if(!g){g={key,title,records:[],authors:[],countries:[],protagonists:[],timestamps:[],verifiedKeys:new Set()};groups.set(key,g)}
    g.records.push(r);
    const author=r.autor_obra||r.autor;if(author&&!g.authors.includes(author))g.authors.push(author);
    if(r.nacionalidade_obra&&String(r.nacionalidade_obra).trim())g.countries.push(countryName(r.nacionalidade_obra));
    (r.protagonistas_obra||[]).forEach(v=>{if(v&&!g.protagonists.includes(v))g.protagonists.push(v)});
    if(r.verificadas&&r.verificadas!=='Pendente')g.timestamps.push(r.verificadas);
    if(r.obra_chave)g.verifiedKeys.add(String(r.obra_chave));
    if(r.obra_verificada&&(!g.title||g.title===r.catalogo||g.title===r.titulo||g.title===r.nome))g.title=r.obra_verificada;
  });
  return [...groups.values()].map(g=>{
    const countries=[...new Set(g.countries.filter(c=>{const key=countryNorm(c);return key!=='pendente'&&!key.startsWith('nao identificad')}))];
    const hasUnidentified=g.countries.some(c=>countryNorm(c).startsWith('nao identificad'));
    g.country=countries.length>1?'Conflito':countries[0]||(hasUnidentified?'Não identificada':'Pendente');
    g.protagonistList=g.protagonists.slice();g.author=g.authors.join(' / ')||'—';g.protagonists=g.protagonistList.join(' / ')||'—';
    g.verified=g.timestamps[0]||'Pendente';g.records.sort((a,b)=>String(a.nome||'').localeCompare(String(b.nome||''),'pt-BR'));
    return g;
  }).sort((a,b)=>a.title.localeCompare(b.title,'pt-BR',{sensitivity:'base'}));
}
function novelIdentityText(value){
  return String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
    .toLocaleLowerCase('pt-BR').replace(/[^\p{L}\p{N}]+/gu,' ').trim().replace(/\s+/g,' ');
}
function novelVolumeTitle(title){
  let value=String(title||'').trim(),previous;
  const prefix=/^(?:vol(?:ume)?|book|livro|tomo|parte?|part)\.?\s*(?:\d+|[ivxlcdm]+)\s*[-–—:]?\s+/i;
  const suffix=/(?:\s+|[\[(]\s*|[-–—:,]\s*)(?:vol(?:ume)?|book|livro|tomo|parte?|part|v)\.?\s*(?:\d+|[ivxlcdm]+)(?:\s*[-–]\s*(?:\d+|[ivxlcdm]+))?\s*[\])]*$/i;
  do{
    previous=value;
    value=value.replace(prefix,'').replace(suffix,'').replace(/[-–—:,]\s*$/,'').trim();
  }while(value!==previous);
  return value;
}
// Três arquivos de volume 1 com nome truncado, junto de volumes confirmados da mesma obra.
const truncatedScumVolumeIds=new Set(['32859','6864','37']);
const desireWorkKeys=new Set(['obra_00842','obra_00898','obra_02641']);
const turbulentWorldKeys=new Set(['obra_00021','obra_00044','obra_00944','obra_01186','obra_01705','obra_02621']);
const horrorGameKeys=new Set(['obra_00200','obra_00774','obra_00775','obra_00945','obra_01135','obra_01136','obra_01254','obra_02398','obra_02524','obra_02595','obra_02604','obra_03018','obra_03019']);
const fClassGuideKeys=new Set(['obra_02103','obra_02108']);
// Chaves conferidas por autor, personagens e referência quando os títulos diferem entre edições.
const chinaAuthorWorkLabels=new Map([
  ["The King's Avatar",['obra_00605','obra_00606','obra_00607','obra_00608','obra_00609','obra_00610','obra_00611','obra_00612','obra_00613','obra_00617','obra_00618','obra_00619','obra_00620','obra_00621','obra_00622','obra_00623','obra_00624']],
  ['S.C.I Mystery Series',['obra_00304','obra_00305','obra_00306','obra_00307','obra_00919','obra_02625']],
  ['After Rebirth, The Real Young Master Began to Maintain His Health',['obra_00786','obra_02000']],
  ['Little Mushroom',['obra_00127','obra_00128','obra_00211','obra_00212','obra_01507','obra_01979','obra_01996']],
  ['The Wife Comes First (Qi Wei Shang)',['obra_00199','obra_00923','obra_01886','obra_01912']],
  ["The Legendary Master's Wife",['obra_00083','obra_00084','obra_00085','obra_00086','obra_00087','obra_00350','obra_02481','obra_02504','obra_02505','obra_02506','obra_02507','obra_02508','obra_02509']],
  ['The Easter Egg Game (The Lucky Egg Game)',['obra_00188','obra_00224','obra_00225','obra_00226','obra_02135','obra_02136']],
  ['Kaleidoscope of Death',['obra_00308','obra_00309','obra_00632','obra_01396','obra_01824','obra_02253','obra_02556','obra_02557','obra_02558','obra_02898']],
  ['Golden Terrace',['obra_00181','obra_00182','obra_00448','obra_00449','obra_00667']],
  ["There's Something Wrong with the Chief (Du Zhu You Bing)",['obra_00302','obra_01069','obra_02312','obra_02835','obra_02842','obra_03003']],
  ['The Husky and His White Cat Shizun',['obra_00018','obra_00357','obra_00418','obra_00644','obra_00645','obra_00672','obra_00776','obra_00777','obra_00828','obra_01063','obra_01066','obra_01334','obra_01347','obra_01348','obra_01661','obra_02477']],
  ['Bat (蝙蝠)',['obra_00705','obra_01559','obra_01560']],
  ['Thousand Autumns',['obra_00030','obra_00205','obra_00823','obra_01689']],
  ['Hidden Love',['obra_02021','obra_02094','obra_02581']],
  ['Descent from an Altitude of 10,000 Meters (The Approach)',['obra_00355','obra_01054','obra_02568','obra_02723']],
  ['Art Thou Ailing? (Jun You Ji Fou)',['obra_01234','obra_01524','obra_02256']],
  ['Golden Jade Dynasty',['obra_01931','obra_01934','obra_01958']],
  ['Ashes (Yan Hui)',['obra_01668','obra_02100']],
  ['At the World’s Mercy',['obra_02088','obra_02257','obra_02697']],
  ['Dawning (After Dawn)',['obra_00551','obra_00959']],
  ['A Letter from Keanu Reeves',['obra_00817','obra_01059','obra_02343','obra_02432','obra_02640','obra_02651','obra_02912']],
  ["The White Cat's Divine Scratching Post",['obra_01581','obra_02315','obra_02829','obra_03006']],
  ['Can Ci Pin (The Defective)',['obra_00183','obra_00222','obra_00293','obra_01079']],
  ['Bottom A, Top O',['obra_00813','obra_01049','obra_02379','obra_02385']],
  ['Fake Slackers',['obra_00473','obra_00474','obra_00487','obra_00488','obra_02520']],
  ['FOG [e-sports]',['obra_00002','obra_01333','obra_01800']],
  ["Chusan's Liuyi Children's Day",['obra_01296','obra_01364','obra_01693','obra_02105','obra_02106','obra_02786','obra_02787']],
  ["Don't Pick Up Boyfriends From the Trash Bin",['obra_02482','obra_02483','obra_02571','obra_02587','obra_02692']],
  ['The Villain’s White Halo',['obra_01448','obra_01980','obra_02731']],
  ['The Plough',['obra_00809','obra_02452']],
  ['A Round Trip to Love',['obra_01670','obra_01672','obra_01673']],
  ['Me to the Universe',['obra_00311','obra_02690']],
  ['Peach Omen',['obra_02358','obra_02422']],
  ['My Beloved Visits My Grave',['obra_01111','obra_01121']],
  ['Blooming Romance',['obra_01349','obra_02896']],
  ['Blade of the Galactic Empire',['obra_01225','obra_01226']],
  ["The Transmigrated Li Jin's Daily Farming Life",['obra_02602','obra_02689']],
  ['Blossoms of Power',['obra_01629','obra_01874']],
  ['Love Beyond the Grave',['obra_01336','obra_01341']],
  ['The Lament of Autumn',['obra_02359','obra_02360']],
  ['After the Disabled God of War Became My Concubine',['obra_02503','obra_02914']],
  ['An Apple',['obra_01434','obra_01660']],
  ['Matrilocal Marriage (Ruzhui)',['obra_00157','obra_02684']],
  ['Wu Chang Jie',['obra_00034','obra_00874']],
  ["The Salted Fish's Political Marriage",['obra_01090','obra_02063']],
  ['Malevolent Curse (Xiong Sui)',['obra_01312','obra_01363']],
  ['Rose and Renaissance',['obra_00943','obra_01165']],
  ['Silent Reading (Mo Du)',['obra_00469','obra_02233']],
  ['Love Spell (Qing Gu)',['obra_01960','obra_02182']],
  ['Paper Plane (Paper Airplane)',['obra_01286','obra_01421']],
  ['Love Out of Sync',['obra_01865','obra_01866']],
  ['Instinct Game',['obra_01744','obra_01746']],
  ['The Love Never Sets',['obra_01152','obra_01190']],
  ['Killer and Healer',['obra_02548','obra_02606']],
  ['The Return of Cambrian Period',['obra_00358','obra_02593']],
  ['I Ship My Adversary X Me',['obra_00654','obra_01470']],
  ['Welcome to the Nightmare Live',['obra_01271','obra_01411','obra_02580','obra_02808']],
  ['Death Progress Bar',['obra_01914','obra_02908']],
  ['Error: Metamorphosis',['obra_02470','obra_02749','obra_02772']],
  ["Don't Hide From Me",['obra_02609','obra_02718']],
  ['How to Survive as a Villain',['obra_01423','obra_01915','obra_02672','obra_02804']],
  ['The Grave Robbers’ Chronicles (Daomu Biji)',['obra_00139','obra_00140']],
  ['The Mystic Nine',['obra_00143','obra_00144','obra_00151']],
  ['The Marquis Is Innocent',['obra_01072','obra_01690']],
  ['The Imperial Uncle',['obra_00025','obra_00208','obra_00638']],
  ['The Rebirth of the General Who Always Sees Himself as a Replacement',['obra_01325','obra_02785']],
  ['Jianghu Demolition Squad',['obra_02400','obra_02708']],
  ['Till Death Do Us Part',['obra_00280','obra_02438']],
  ['My Husband and I Sleep in a Coffin',['obra_02414','obra_02528']],
  ['This Venerable One Really Didn’t Abandon My Familiar',['obra_02719','obra_02721']],
  ['The Sickly Beauty Substitute Called It Quits',['obra_02513','obra_02514','obra_02515']],
  ['The Sword Named No Way Out',['obra_00629','obra_02982']],
  ['The Blind Concubine',['obra_00049','obra_00877','obra_01124']],
  ['[Quick Transmigration] The Delicate Little Beauty Keeps Getting Caught',['obra_01775','obra_01843']]
].flatMap(([title,keys])=>keys.map(key=>[key,title])));
function novelSeriesFamily(group){
  const reviewedKey=group.key.startsWith('obra:')?group.key.slice(5):'';
  if(group.country==='China'&&chinaAuthorWorkLabels.has(reviewedKey))
    return chinaAuthorWorkLabels.get(reviewedKey);
  if(group.records.length&&group.records.every(record=>fClassGuideKeys.has(String(record.obra_chave))))
    return 'Let This F-Class Guide Live in Peace!';
  if(novelIdentityText(group.title)==='the scum villain s self 1'&&group.records.length&&
    group.records.every(record=>truncatedScumVolumeIds.has(String(record.id))&&!record.obra_chave))
    return 'The Scum Villain’s Self-Saving System';
  if(group.records.length&&group.records.every(record=>desireWorkKeys.has(String(record.obra_chave))))
    return 'Desire (垂涎)';
  if(group.records.length&&group.records.every(record=>turbulentWorldKeys.has(String(record.obra_chave))))
    return 'To Rule in a Turbulent World (乱世为王)';
  if(group.records.length&&group.records.every(record=>horrorGameKeys.has(String(record.obra_chave))))
    return 'I Became a God in a Horror Game';
  const identity=novelIdentityText(group.title);
  const author=group.authors.length===1?novelIdentityText(group.authors[0]):'';
  if(identity.includes('2022 zhongyuan mini theatre'))return '';
  if(group.country==='Coreia do Sul'){
    if(/^boy season(?: |$)/.test(author)&&/^(?:code name|codename) anastasia(?: novel| https t me [\p{L}\p{N} ]+)?$/u.test(identity))
      return 'Codename Anastasia';
    if(/^suji kim(?: |$)/.test(author)&&/^under the oak tree(?:$| esp$| season [12] [0-9]+$)/.test(identity))
      return 'Under the Oak Tree';
  }
  const text=[group.title,...group.records.map(r=>r.obra_verificada||r.catalogo||r.titulo||'')].join(' ').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
  if(/fanfic|fanfiction/.test(text))return '';
  if(/\bfor a thousand autum(?:n)?s\b/.test(text))return '';
  const rules=[
    ['Grandmaster of Demonic Cultivation',/grandmaster of demonic cultivation|mo dao zu shi|el gran maestro de la cultivacion demoniaca|魔道祖师/],
    ['Heaven Official’s Blessing',/heaven official.s blessing|tian guan ci fu|la bendicion del oficial del cielo|la benedizione dell.?ufficiale divino|天官赐福/],
    ['The Apothecary Diaries',/apothecary diaries/],['10 DANCE',/\b10 dance\b/],['Thousand Autumns',/thousand autumns|qian qiu/],
    ['Hate Me, but Let Me Stay',/hate me but let me stay/],['The Moon on a Rainy Night',/moon on a rainy night/],['The Summer You Were There',/summer you were there/],
    ['Joyful Reunion',/joyful reunion/],['Lullaby of the Dawn',/lullaby of the dawn/],['The Husky and His White Cat Shizun',/husky and his white cat shizun|erha he ta de bai mao/],
    ['Dinghai Fusheng Records',/dinghai fusheng records/],['Peerless',/\bpeerless\b/],['World’s End Blue Bird',/world.s end blue bird/],['No God in Eden',/no god in eden/],
    ['Remnants of Filth (Yuwu)',/remnants of filth|\byuwu\b/],['Run Away With Me, Girl',/run away with me girl/],['Run Wild (Sa Ye)',/run wild|\bsa ye\b/],
    ['Stars of Chaos (Sha Po Lang)',/stars of chaos|sha po lang/],['Silent Reading (Mo Du)',/silent reading|\bmo du\b/],['The Dangerous Convenience Store',/dangerous convenience store/],
    ['Three Hundred Years of Longing',/three hundred years of longing|unseen immortal of (?:three hundred|300) years|bu jian shang xian san bai nian|不见上仙三百年/],['Thrice Married to a Salted Fish',/thrice married to a salted fish/],['Ballad of Sword and Wine (Qiang Jin Jiu)',/ballad of sword and wine|qiang jin jiu/],
    ['Case File Compendium (Bing An Ben)',/case file compendium|bing an ben/],['Guardian (Zhen Hun)',/guardian zhen hun|\bzhen hun\b/],
    ['Legend of Exorcism (Tianbao Fuyao Lu)',/legend of exorcism|tianbao fuyao lu/],['Copper Coins (Tong Qian Kan Shi)',/copper coin(?:s| niches)?|tong qian kan shi|monedas de cobre|铜钱龛世/],
    ['The Wife Comes First (Qi Wei Shang)',/wife comes first|qi wei shang/],['Twin Jades of Jiangdong',/twin jades of jiangdong/],['Villains Are Destined to Die',/villains are destined to die/],
    ['The Summer Hikaru Died',/summer hikaru died/],['You’ve Got Mail',/you.ve got mail|perils of pigeon post/],['Your Forma',/your forma|electronic investigator echika/],
    ['The Disabled Tyrant’s Beloved Pet Fish',/disabled tyrant.s beloved pet fish|canji baojun de zhangxin yu/],['Secrets of the Silent Witch',/secrets of the silent witch/],
    ['Lord of Mysteries',/lord of (?:the )?mysteries/],['Eiderdown',/\beiderdown\b/],['Golden Terrace',/golden terrace/],['Hell Is Dark with No Flowers',/hell is dark with no flowers/],
    ['Hidden Love',/\bhidden love\b/],['Interminable',/\binterminable\b/],['Look at Me',/^look at me(?: |$)/],['Love Between Fairy and Devil',/love between fairy and devil/],
    ['Omniscient Reader’s Viewpoint',/omniscient readers? viewpoint/],['Panguan: The Twelfth Gate',/panguan|twelfth gate/],['The Only Sunflower I See Is You',/only sunflower i see is you/],
    ['The Villain’s White Halo',/villain.s white halo/],['At the World’s Mercy',/at the world.s mercy/],['Deadman Switch',/deadman switch/],
    ['Go For It, Nakamura!',/go for it(?: again)? nakamura/],['Earthian',/\bearthian\b/],['Megumi & Tsugumi',/megumi.*tsugumi/],['School Trip: Joined a Group I’m Not Close To',/school trip joined a group/],
    ['Strawberry Panic!',/strawberry panic/],['Rose & Renaissance',/rose renaissance/],['Trascendiendo la Semilla del Mal',/trascendiendo la semilla del mal/],
    ['The Scum Villain’s Self-Saving System',/scum villain.s self[- ]?saving system|ren zha fanpai zijiu xitong|\bsvss\b|el sistema de autosalvacion del villano escoria|il sistema di salvataggio del peggiore dei cattivi|人渣反派自救系统/],
    ['Yin Ke',/\byin ke\b|阴客/],
    ['A Certain Someone',/\ba certain someone\b|\bmou mou\b|某某/],
    ['Black Sky',/black sk(?:y|ay)|hei ?tian|黑天/],
    ['First-Class Lawyer',/first[- ]class lawyer/],
    ['Global University Entrance Examination',/global examination|global university entrance examination/]
  ];
  for(const [label,pattern] of rules){if(pattern.test(text)){if(label==='The Scum Villain’s Self-Saving System'&&/bingjiu|fanfic|fanfiction/.test(text))return '';return label}}
  const protagonistText=(group.protagonistList||[]).join(' ').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
  const protagonistFamilies=[
    ['Grandmaster of Demonic Cultivation',/wei wuxian|魏无羡/,/lan wangji|蓝忘机/],
    ['Heaven Official’s Blessing',/xie lian|谢怜/,/hua cheng|花城/],
    ['The Scum Villain’s Self-Saving System',/shen qingqiu|shen yuan|沈清秋/,/luo binghe|洛冰河/],
    ['Yin Ke',/xie bai|谢白/,/yin wushu|殷无书/],
    ['A Certain Someone',/sheng wang|盛望/,/jiang tian|江添/],
    ['Black Sky',/chu si|楚斯/,/sa.?e yang|萨厄.?杨/],
    ['Copper Coins (Tong Qian Kan Shi)',/xue xian|薛闲/,/xuan min|玄悯/],
    ['First-Class Lawyer',/yan suizhi|燕绥之/,/gu yan|顾晏/],
    ['Global University Entrance Examination',/you huo|游惑/,/qin jiu|秦究/],
    ['Panguan: The Twelfth Gate',/wen shi|闻时/,/xie wen|谢问/],
    ['Three Hundred Years of Longing',/wu xingxue|乌行雪|吴星雪/,/xiao fuxuan|萧复暄/]
  ];
  for(const [label,first,second] of protagonistFamilies){if(first.test(protagonistText)&&second.test(protagonistText)){if(label==='The Scum Villain’s Self-Saving System'&&/bingjiu|fanfic|fanfiction/.test(text))return '';return label}}
  return '';
}
function groupNovelSeries(groups){
  const families=new Map();
  groups.forEach(group=>{const family=novelSeriesFamily(group);if(!family)return;if(!families.has(family))families.set(family,[]);families.get(family).push(group)});
  const consumed=new Set(),result=[];
  for(const [family,members] of families){
    if(members.length<2)continue;
    members.forEach(member=>consumed.add(member));
    const records=members.flatMap(member=>member.records);
    const unique=values=>[...new Set(values.filter(Boolean))];
    const turbulent=family==='To Rule in a Turbulent World (乱世为王)';
    const authors=turbulent?['Fei Tian Ye Xiang (非天夜翔)']:unique(members.flatMap(member=>member.authors));
    const protagonists=turbulent?['You Miao','Li Zhifeng']:(family==='I Became a God in a Horror Game'?
      ['Bai Liu (白柳)','Xie Ta (谢塔)']:(family==='The Imperial Uncle'?
      ['Cheng Jun (Prince Huai)','Liu Tongyi']:(family==='The Mystic Nine'?
      []:unique(members.flatMap(member=>member.protagonistList)))));
    const countries=unique(members.map(member=>member.country).filter(country=>country!=='Pendente'&&country!=='Não identificada'&&country!=='Conflito'));
    const timestamps=unique(members.map(member=>member.verified).filter(value=>value&&value!=='Pendente'));
    const titles=unique(members.flatMap(member=>[member.title,...member.records.map(r=>r.obra_verificada||r.catalogo||r.titulo||'')]).filter(title=>title&&title!==family));
    if(family==='Desire (垂涎)')titles.push('ABO Desire');
    if(turbulent)titles.push('LSWW','Luanshi Wei Wang');
    result.push({key:'serie:'+family,title:family,records,authors,countries,protagonistList:protagonists,author:authors.join(' / ')||'—',protagonists:protagonists.join(' / ')||'—',country: new Set(members.map(member=>member.country).filter(value=>value!=='Pendente')).size>1&&countries.length>1?'Conflito':(countries[0]||members.find(member=>member.country==='Não identificada')?.country||'Pendente'),verified:timestamps[0]||'Pendente',alternateTitles:titles});
  }
  return [...groups.filter(group=>!consumed.has(group)),...result].sort((a,b)=>a.title.localeCompare(b.title,'pt-BR',{sensitivity:'base'}));
}
// Etapas por nacionalidade: mesmo autor e título idêntico após retirar apenas o número do volume.
function groupCountryVolumes(groups,country){
  const buckets=new Map();
  groups.forEach(group=>{
    if(group.country!==country||group.authors.length!==1)return;
    const author=novelIdentityText(group.authors[0]);
    const base=novelIdentityText(novelVolumeTitle(group.title));
    if(!author||['pendente','nao identificado','desconhecido','unknown'].includes(author)||base.length<6)return;
    const key=country+'|'+author+'|'+base;
    if(!buckets.has(key))buckets.set(key,[]);
    buckets.get(key).push(group);
  });
  const consumed=new Set(),merged=[];
  for(const [key,members] of buckets){
    if(members.length<2)continue;
    members.forEach(member=>consumed.add(member));
    const unique=values=>[...new Set(values.filter(Boolean))];
    const plain=members.find(member=>novelVolumeTitle(member.title)===member.title.trim());
    const title=plain?plain.title:novelVolumeTitle(members[0].title);
    const records=members.flatMap(member=>member.records)
      .sort((a,b)=>String(a.nome||'').localeCompare(String(b.nome||''),'pt-BR'));
    const authors=unique(members.flatMap(member=>member.authors));
    const protagonistList=unique(members.flatMap(member=>member.protagonistList));
    const alternateTitles=unique(members.flatMap(member=>[member.title,...(member.alternateTitles||[])]))
      .filter(value=>value!==title);
    merged.push({key:'volume:'+key,title,records,authors,countries:[country],protagonistList,
      author:authors.join(' / ')||'—',protagonists:protagonistList.join(' / ')||'—',country,
      verified:members.find(member=>member.verified&&member.verified!=='Pendente')?.verified||'Pendente',
      alternateTitles});
  }
  return [...groups.filter(group=>!consumed.has(group)),...merged];
}
function novelSpecificReference(value){
  let url;
  try{url=new URL(String(value||''))}catch{return ''}
  const host=url.hostname.toLowerCase().replace(/^www\./,'');
  if(host==='novelupdates.com'){
    const match=url.pathname.match(/^\/series\/([^/]+)\/?$/i);
    return match?'nu:'+match[1].toLowerCase():'';
  }
  if(/(^|\.)jjwxc\.(?:net|com)$/.test(host)){
    const id=url.searchParams.get('novelid')||url.pathname.match(/^\/book2\/(\d+)(?:\/|$)/)?.[1]||'';
    return /^\d+$/.test(id)?'jjwxc:'+id:'';
  }
  return '';
}
const chinaReferenceTitles=new Map([
  ['nu:case-file-compendium','Case File Compendium (Bing An Ben)'],
  ['nu:the-husky-and-his-white-cat-shizun','The Husky and His White Cat Shizun'],
  ['nu:the-kings-avatar',"The King's Avatar"],
  ['nu:global-survival-from-a-small-wooden-cabin-to-a-magic-farm','Global Survival: From a Small Wooden Cabin to a Magic Farm'],
  ['jjwxc:379995','S.C.I Mystery Series'],
  ['jjwxc:6947226','After Rebirth, The Real Young Master Began to Maintain His Health']
]);
function groupChinaByReference(groups){
  const parent=groups.map((_,index)=>index);
  const root=index=>{while(parent[index]!==index){parent[index]=parent[parent[index]];index=parent[index]}return index};
  const buckets=new Map(),references=groups.map(()=>new Set());
  groups.forEach((group,index)=>{
    if(group.country!=='China'||group.authors.length!==1)return;
    const author=novelIdentityText(group.authors[0]);
    if(!author||['pendente','nao identificado','desconhecido','unknown'].includes(author))return;
    for(const record of group.records){
      const ref=novelSpecificReference(record.referencia_obra||record.fonte_nacionalidade_obra);
      if(!ref||ref==='jjwxc:2516402')continue;
      references[index].add(ref);
      const key=author+'|'+ref;
      if(!buckets.has(key))buckets.set(key,[]);
      if(!buckets.get(key).includes(index))buckets.get(key).push(index);
    }
  });
  for(const members of buckets.values()){
    if(members.length<2)continue;
    const first=root(members[0]);
    members.slice(1).forEach(index=>{parent[root(index)]=first});
  }
  const components=new Map();
  groups.forEach((group,index)=>{
    const key=root(index);if(!components.has(key))components.set(key,[]);
    components.get(key).push({group,index});
  });
  const unique=values=>[...new Set(values.filter(Boolean))];
  const titlePenalty=group=>{
    const title=String(group.title||'');
    let penalty=group.key.startsWith('serie:')?-20:0;
    if(/^[a-f0-9]{24,64}$/i.test(title)||/^input$/i.test(title))penalty+=100;
    if(/https?:|@|z[- ]?library|bokgen|pdfcoffee|\b(?:vol(?:ume)?|book|chapter|part|extras?|anthology|complete|completed|edition|season|mtl|esp)\b|#\d/i.test(title))penalty+=20;
    return penalty+title.length/1000;
  };
  const result=[];
  for(const component of components.values()){
    if(component.length===1){result.push(component[0].group);continue}
    const members=component.map(item=>item.group);
    const preferred=members.slice().sort((a,b)=>titlePenalty(a)-titlePenalty(b))[0];
    const refs=unique(component.flatMap(item=>[...references[item.index]]));
    const title=refs.map(ref=>chinaReferenceTitles.get(ref)).find(Boolean)||preferred.title;
    const records=members.flatMap(member=>member.records)
      .sort((a,b)=>String(a.nome||'').localeCompare(String(b.nome||''),'pt-BR'));
    const authors=unique(members.flatMap(member=>member.authors));
    const protagonistSource=members.slice().sort((a,b)=>b.records.length-a.records.length)
      .find(member=>member.protagonistList?.length>=2&&member.protagonistList.every(value=>value!=='Pendente'));
    const protagonistList=protagonistSource?protagonistSource.protagonistList.slice():
      unique(members.flatMap(member=>member.protagonistList));
    const alternateTitles=unique(members.flatMap(member=>[member.title,...(member.alternateTitles||[])]))
      .filter(value=>value!==title);
    result.push({key:'fonte:'+members.map(member=>member.key).sort()[0],title,records,authors,
      countries:['China'],protagonistList,author:authors.join(' / ')||'—',
      protagonists:protagonistList.join(' / ')||'—',country:'China',
      verified:members.find(member=>member.verified&&member.verified!=='Pendente')?.verified||'Pendente',
      alternateTitles});
  }
  return result;
}
const novelGroups=groupChinaByReference(['China','Coreia do Sul','Estados Unidos'].reduce(
  (groups,country)=>groupCountryVolumes(groups,country),groupNovelSeries(makeNovelGroups(DATA.records))))
  .sort((a,b)=>a.title.localeCompare(b.title,'pt-BR',{sensitivity:'base'}));
let filtered=novelGroups.slice(),page=0,novelSummaryPage=0;
const selectedNovelCountries=new Set(),selectedNovelAuthors=new Set();
let novelSidebarFacet='country';
let novelQuantityFilter='all',selectedNovelAuthor='',selectedNovelProtagonist='';
const pageSize=50;
let novelSummaryPageSize=10;

function navigate(view){
  if(!['overview','novels'].includes(view))view='overview';
  const pageView=view==='novels'?'overview':view;
  for(const name of ['overview','explorer'])$(name).classList.toggle('hidden',name!==pageView);
  $('overviewPanel').classList.toggle('hidden',view!=='overview');
  $('novelsPanel').classList.toggle('hidden',view!=='novels');
  for(const name of ['overview','novels'])$('nav-'+name).classList.toggle('active',name===view);
  location.hash=view;
}
function metric(label,value){
  return '<div class="card"><div class="label">'+esc(label)+
    '</div><div class="number">'+fmt(value)+'</div></div>';
}
const obraOrigins=(()=>{
  const country_details={};
  for(const group of novelGroups){
    if(['Pendente','Não identificada','Conflito','INDEFINIDO'].includes(group.country))continue;
    const entry=country_details[group.country]||(country_details[group.country]={work_count:0,epub_count:0});
    entry.work_count++;
    entry.epub_count+=group.records.length;
  }
  const details=Object.values(country_details);
  return {work_count:details.reduce((sum,item)=>sum+item.work_count,0),
    epub_count:details.reduce((sum,item)=>sum+item.epub_count,0),country_details};
})();
const total=DATA.records.length;
$('cards').innerHTML=
  metric('EPUBs locais confirmados',total)+
  metric('Obras com origem classificada',obraOrigins.work_count)+
  metric('EPUBs com origem classificada',obraOrigins.epub_count);
$('verifiedOriginsSummary').textContent=
  fmt(obraOrigins.work_count)+' obras · '+fmt(obraOrigins.epub_count)+
  ' EPUBs associados';
function renderOriginsDonut(){
  const details=obraOrigins.country_details||{};
  let entries=Object.entries(details).map(([country,value])=>({country:countryName(country),works:Number(value.work_count||0),epubs:Number(value.epub_count||0)}));
  if(!entries.length)entries=Object.entries(obraOrigins.countries||{}).map(([country,works])=>({country:countryName(country),works:Number(works||0),epubs:0}));
  const merged=new Map();entries.forEach(item=>{const old=merged.get(item.country)||{country:item.country,works:0,epubs:0};old.works+=item.works;old.epubs+=item.epubs;merged.set(item.country,old)});
  entries=[...merged.values()].filter(item=>item.works>0).sort((a,b)=>b.works-a.works);
  if(!entries.length){$('verifiedOrigins').innerHTML='<p class="muted">Nenhuma origem classificada.</p>';return}
  const top=entries.slice(0,6),rest=entries.slice(6);
  if(rest.length)top.push({country:'Outros ('+rest.length+' países)',works:rest.reduce((n,x)=>n+x.works,0),epubs:rest.reduce((n,x)=>n+x.epubs,0)});
  const colors=['#3863e9','#4ba5df','#805be8','#eda33a','#50b58c','#df4f98','#98a5b8'];
  const total=top.reduce((n,x)=>n+x.works,0),radius=76,circ=2*Math.PI*radius;
  let offset=0;
  const segments=top.map((item,index)=>{const length=circ*item.works/total;const color=colors[index%colors.length];const pct=(100*item.works/total).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1});const start=offset;offset+=length;return '<circle class="donut-segment" cx="100" cy="100" r="'+radius+'" stroke="'+color+'" stroke-dasharray="'+length+' '+(circ-length)+'" stroke-dashoffset="'+(-start)+'" transform="rotate(-90 100 100)" tabindex="0" role="img" aria-label="'+esc(item.country+': '+fmt(item.works)+' obras e '+fmt(item.epubs)+' EPUBs')+'" data-country="'+esc(item.country)+'" data-works="'+item.works+'" data-epubs="'+item.epubs+'"><title>'+esc(item.country+' · '+fmt(item.works)+' obras · '+fmt(item.epubs)+' EPUBs · '+pct+'%')+'</title></circle>'}).join('');
  const legend=top.map((item,index)=>'<div class="donut-legend-item"><i class="donut-swatch" style="background:'+colors[index%colors.length]+'"></i><span>'+esc(item.country)+'</span><span class="donut-legend-count">'+fmt(item.works)+' obras<span>'+fmt(item.epubs)+' EPUBs</span></span></div>').join('');
  $('verifiedOrigins').innerHTML='<div class="donut-layout"><div class="donut-viz"><svg viewBox="0 0 200 200" role="img" aria-label="Distribuição das obras por origem"><circle cx="100" cy="100" r="'+radius+'" fill="none" stroke="#e7edf5" stroke-width="32"></circle>'+segments+'</svg><div class="donut-center"><strong>'+fmt(obraOrigins.work_count)+'</strong><span>obras com origem</span></div></div><div class="donut-legend">'+legend+'</div></div>';
  const tooltip=$('donutTooltip');
  document.querySelectorAll('.donut-segment').forEach(segment=>{
    const show=event=>{tooltip.innerHTML='<strong>'+esc(segment.dataset.country)+'</strong><br>'+fmt(segment.dataset.works)+' obras<br>'+fmt(segment.dataset.epubs)+' EPUBs';tooltip.style.display='block';const x=event.clientX??window.innerWidth/2,y=event.clientY??window.innerHeight/2;tooltip.style.left=Math.min(x+14,window.innerWidth-270)+'px';tooltip.style.top=Math.min(y+14,window.innerHeight-100)+'px'};
    segment.addEventListener('pointerenter',show);segment.addEventListener('pointermove',show);segment.addEventListener('pointerleave',()=>tooltip.style.display='none');segment.addEventListener('focus',show);segment.addEventListener('blur',()=>tooltip.style.display='none');
  });
}
renderOriginsDonut();
const cherrymistCatalog=[
  {title:"Almost, But Not Quite",url:"https://www.novelupdates.com/series/almost-but-not-quite/",epubId:"74000",evidenceUrl:"https://cherrymist.cafe/story/almost-but-not-quite/"},
  {title:"Binding Flower",url:"https://fullnovels.com/binding-flower/",epubId:"89102",evidenceUrl:"https://cherrymist.cafe/story/binding-flower/"},
  {title:"Hell Execution Order",url:"https://fullnovels.com/hell-execution-order/",epubId:"89272",evidenceUrl:"https://cherrymist.cafe/chapter/heo-ch1/"},
  {title:"Lumen Project",url:"https://fullnovels.com/lumen-project/",epubId:"80402",evidenceUrl:"https://cherrymist.cafe/story/lumen-project/"}
];
const cherrymistRecordsById=new Map(DATA.records.map(record=>[String(record.id),record]));
function renderCherrymistMatches(){
  const matches=cherrymistCatalog.map(item=>({...item,records:[cherrymistRecordsById.get(item.epubId)].filter(Boolean)})).filter(item=>item.records.length);
  $('cherrymistSummary').textContent=matches.length+' EPUBs locais com referência direta ao site Cherry Mist no próprio arquivo. A listagem anexa não cobre todos os títulos do grupo.';
  $('cherrymistBody').innerHTML=matches.map(item=>{
    const inventoryTitles=[...new Set(item.records.map(record=>record.obra_verificada||record.catalogo||record.titulo||record.nome).filter(Boolean))];
    const authors=[...new Set(item.records.map(record=>record.autor_obra||record.autor).filter(Boolean))];
    const countries=[...new Set(item.records.map(record=>record.nacionalidade_obra||record.pais).filter(Boolean).map(countryName))];
    const files=item.records.map(record=>'<span class="cherrymist-file">'+esc(record.nome||'Arquivo sem nome')+' · ID '+esc(record.id||'—')+'</span>').join('');
    return '<tr><td><a href="'+esc(item.url)+'" target="_blank" rel="noopener noreferrer">'+esc(item.title)+'</a></td><td>'+esc(inventoryTitles.join(' / ')||'—')+'</td><td>'+esc(authors.join(' / ')||'—')+'</td><td>'+esc(countries.join(' / ')||'—')+'</td><td>'+files+'</td><td><a href="'+esc(item.evidenceUrl)+'" target="_blank" rel="noopener noreferrer">Ver referência</a></td></tr>';
  }).join('')||'<tr><td colspan="6" class="muted">Nenhum EPUB local com referência direta ao site Cherry Mist.</td></tr>';
}
renderCherrymistMatches();
function renderNovelSummary(){
  const query=$('novelSummarySearch').value.trim().toLocaleLowerCase('pt-BR');
  const rows=novelGroups.filter(g=>
    (!query||[g.title,...(g.alternateTitles||[]),...g.records.flatMap(r=>[r.obra_verificada,r.catalogo,r.titulo,r.nome])].filter(Boolean).some(value=>String(value).toLocaleLowerCase('pt-BR').includes(query)))&&
    (!selectedNovelCountries.size||selectedNovelCountries.has(g.country))&&
    (!selectedNovelAuthors.size||novelGroupAuthors(g).some(author=>selectedNovelAuthors.has(author)))&&
    (!selectedNovelAuthor||g.authors.includes(selectedNovelAuthor))&&
    (!selectedNovelProtagonist||g.protagonistList.includes(selectedNovelProtagonist))&&
    (novelQuantityFilter==='all'||(novelQuantityFilter==='one'?g.records.length===1:g.records.length>1))
  );
  const pages=Math.max(1,Math.ceil(rows.length/novelSummaryPageSize));novelSummaryPage=Math.min(novelSummaryPage,pages-1);
  const start=novelSummaryPage*novelSummaryPageSize,shown=rows.slice(start,start+novelSummaryPageSize);
  $('novelSummaryBody').innerHTML=shown.map((g,index)=>{
    const detailId='novel-summary-detail-'+index;
    const pending=/^(pendente|não identificada|nao identificada)/i.test(g.country);
    const factsRecord=g.records.find(r=>r.tipo_obra||r.titulo_original_obra||r.sinopse_obra);
    const facts=factsRecord?[["Formato",factsRecord.tipo_obra],["Título original",factsRecord.titulo_original_obra],["Enredo",factsRecord.sinopse_obra]].filter(([,value])=>value).map(([label,value])=>'<div class="novel-work-fact"><strong>'+esc(label)+'</strong><span>'+esc(value)+'</span></div>').join(''):'';
    const files=g.records.map(r=>{const sourceTitle=r.obra_verificada||r.catalogo||r.titulo||'';return '<div class="novel-file-item"><span class="novel-file-name"><span class="novel-file-icon" aria-hidden="true">▤</span><span>'+((sourceTitle&&groupNorm(sourceTitle)!==groupNorm(g.title))?'<small>'+esc(sourceTitle)+'</small><br>':'')+esc(r.nome||'—')+'</span></span><span class="novel-file-id">ID #'+esc(r.id||'—')+'</span></div>'}).join('');
    return `<tr class="novel-summary-row" tabindex="0" aria-expanded="false" aria-controls="${detailId}" onclick="toggleNovelSummaryRow(this)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleNovelSummaryRow(this)}"><td><div class="novel-summary-title"><span>${esc(g.title)}</span></div></td><td>${esc(g.author==='—'?'Pendente':g.author)}</td><td>${esc(g.protagonists==='—'?'Pendente':g.protagonists)}</td><td><span class="novel-country-badge ${pending?'pending':''}">${esc(g.country)}</span></td><td><span class="novel-count-badge ${g.records.length>1?'multiple':''}">${fmt(g.records.length)}</span></td><td><span class="novel-summary-expand" aria-hidden="true">›</span></td></tr><tr id="${detailId}" class="novel-summary-detail" hidden><td colspan="6"><div class="novel-files">${facts?'<div class="novel-work-facts">'+facts+'</div>':''}<div class="novel-file-list">${files}</div></div></td></tr>`;
  }).join('')||'<tr><td colspan="6" class="muted">Nenhum grupo encontrado com esses filtros.</td></tr>';
  const end=Math.min(start+novelSummaryPageSize,rows.length);
  $('novelSummaryRange').textContent=rows.length?fmt(start+1)+'–'+fmt(end)+' de '+fmt(rows.length):'0 de 0';
  $('novelSummaryPageLabel').textContent=(novelSummaryPage+1)+' / '+pages;
  $('novelSummaryPrev').disabled=novelSummaryPage===0;$('novelSummaryNext').disabled=novelSummaryPage>=pages-1;
  $('novelPageSize').value=String(novelSummaryPageSize);
}
function moveNovelSummary(delta){novelSummaryPage+=delta;renderNovelSummary()}
function setNovelPageSize(value){novelSummaryPageSize=Number(value)||10;novelSummaryPage=0;renderNovelSummary()}
function novelGroupAuthors(group){return group.authors.length?group.authors:['Pendente']}
function setNovelSidebarFacet(type){novelSidebarFacet=type==='author'?'author':'country';const isAuthor=novelSidebarFacet==='author';$('novel-facet-country').setAttribute('aria-pressed',String(!isAuthor));$('novel-facet-author').setAttribute('aria-pressed',String(isAuthor));$('novelFacetSearch').value='';$('novelFacetSearch').placeholder=isAuthor?'Buscar autor...':'Filtrar origem...';$('novelFacetSearch').setAttribute('aria-label',isAuthor?'Buscar autor':'Filtrar origem');renderNovelFacetFilters()}
function renderNovelFacetFilters(){
  const isAuthor=novelSidebarFacet==='author',query=$('novelFacetSearch').value.trim().toLocaleLowerCase('pt-BR'),counts=new Map();
  novelGroups.forEach(g=>{const values=isAuthor?novelGroupAuthors(g):[g.country];[...new Set(values)].forEach(value=>counts.set(value,(counts.get(value)||0)+1))});
  const values=[...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'pt-BR',{sensitivity:'base'})).filter(([value])=>value.toLocaleLowerCase('pt-BR').includes(query));
  const selected=isAuthor?selectedNovelAuthors:selectedNovelCountries;
  $('novelFacetFilters').innerHTML=values.map(([value,count])=>'<label class="novel-facet-option"><input type="checkbox" value="'+esc(value)+'" '+(selected.has(value)?'checked':'')+' onchange="toggleNovelSidebarFilter(this)"><span>'+esc(value)+'</span><span class="novel-facet-count">'+fmt(count)+'</span></label>').join('')||'<div class="muted" style="padding:8px 6px">Nenhum resultado.</div>';
}
function toggleNovelSidebarFilter(input){const selected=novelSidebarFacet==='author'?selectedNovelAuthors:selectedNovelCountries;if(input.checked)selected.add(input.value);else selected.delete(input.value);novelSummaryPage=0;renderNovelSummary()}
function novelDropdownValues(type){
  const counts=new Map();
  novelGroups.forEach(g=>{const values=type==='author'?g.authors:g.protagonistList;[...new Set(values)].filter(Boolean).forEach(value=>counts.set(value,(counts.get(value)||0)+1))});
  return [...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'pt-BR',{sensitivity:'base'}));
}
function renderNovelDropdown(type){
  const name=type==='author'?'author':'protagonist',query=$('novel-'+name+'-search').value.trim().toLocaleLowerCase('pt-BR');
  const selected=type==='author'?selectedNovelAuthor:selectedNovelProtagonist;
  const allLabel=type==='author'?'Autores':'Protagonista';
  const options=[['',allLabel,novelGroups.length],...novelDropdownValues(type).map(([value,count])=>[value,value,count])].filter(item=>!query||String(item[0]||item[1]).toLocaleLowerCase('pt-BR').includes(query));
  $('novel-'+name+'-options').innerHTML=options.map(([value,label,count])=>'<button type="button" class="novel-custom-option" role="option" aria-selected="'+String(value===selected)+'" data-value="'+esc(value)+'" onclick="selectNovelFacet(\''+type+'\',this.dataset.value)"><span>'+esc(value||label)+'</span><span class="novel-custom-option-count">'+fmt(count)+'</span></button>').join('')||'<div class="muted" style="padding:8px">Nenhum resultado.</div>';
}
function toggleNovelDropdown(type){const name=type==='author'?'author':'protagonist',menu=$('novel-'+name+'-menu'),opening=menu.hidden;['author','protagonist'].forEach(key=>{$('novel-'+key+'-menu').hidden=true;$('novel-'+key+'-button').setAttribute('aria-expanded','false')});if(opening){menu.hidden=false;$('novel-'+name+'-button').setAttribute('aria-expanded','true');renderNovelDropdown(type);$('novel-'+name+'-search').focus()}}
function selectNovelFacet(type,value){if(type==='author'){selectedNovelAuthor=value;$('novel-author-label').textContent=value||'Autores'}else{selectedNovelProtagonist=value;$('novel-protagonist-label').textContent=value||'Protagonista'};toggleNovelDropdown(type);novelSummaryPage=0;renderNovelSummary()}
function setNovelQuantityFilter(value){novelQuantityFilter=value;novelSummaryPage=0;document.querySelectorAll('[data-epub-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.epubFilter===value)));renderNovelSummary()}
function clearNovelFilters(){selectedNovelCountries.clear();selectedNovelAuthors.clear();selectedNovelAuthor='';selectedNovelProtagonist='';novelQuantityFilter='all';$('novelSummarySearch').value='';$('novelFacetSearch').value='';$('novel-author-search').value='';$('novel-protagonist-search').value='';novelSummaryPage=0;document.querySelectorAll('[data-epub-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.epubFilter==='all')));$('novel-author-label').textContent='Autores';$('novel-protagonist-label').textContent='Protagonista';['author','protagonist'].forEach(key=>{$('novel-'+key+'-menu').hidden=true;$('novel-'+key+'-button').setAttribute('aria-expanded','false')});renderNovelFacetFilters();renderNovelSummary()}
document.addEventListener('click',event=>{if(!event.target.closest('.novel-custom-select'))['author','protagonist'].forEach(key=>{$('novel-'+key+'-menu').hidden=true;$('novel-'+key+'-button').setAttribute('aria-expanded','false')})});
function toggleNovelSummaryRow(row){const detail=$(row.getAttribute('aria-controls'));const expanded=row.getAttribute('aria-expanded')==='true';row.setAttribute('aria-expanded',String(!expanded));detail.hidden=expanded}
function exportNovelSummaryCSV(){
  const query=$('novelSummarySearch').value.trim().toLocaleLowerCase('pt-BR');
  const groups=novelGroups.filter(g=>(!query||[g.title,...(g.alternateTitles||[]),...g.records.flatMap(r=>[r.obra_verificada,r.catalogo,r.titulo,r.nome])].filter(Boolean).some(value=>String(value).toLocaleLowerCase('pt-BR').includes(query)))&&(!selectedNovelCountries.size||selectedNovelCountries.has(g.country))&&(!selectedNovelAuthors.size||novelGroupAuthors(g).some(author=>selectedNovelAuthors.has(author)))&&(!selectedNovelAuthor||g.authors.includes(selectedNovelAuthor))&&(!selectedNovelProtagonist||g.protagonistList.includes(selectedNovelProtagonist))&&(novelQuantityFilter==='all'||(novelQuantityFilter==='one'?g.records.length===1:g.records.length>1)));
  const cols=['Obra','Autor','Protagonistas','Origem','Quantidade de EPUBs','Arquivo EPUB','ID'];
  const quote=value=>'"'+String(value??'').replace(/"/g,'""')+'"';
  const lines=[cols.join(';'),...groups.flatMap(g=>g.records.map(r=>[g.title,g.author==='—'?'Pendente':g.author,g.protagonists==='—'?'Pendente':g.protagonists,g.country,g.records.length,r.nome||'',r.id||''].map(quote).join(';')))];
  const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download='epubs_por_novel.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
renderNovelFacetFilters();
renderNovelDropdown('author');renderNovelDropdown('protagonist');
renderNovelSummary();
const nationalities=new Map();
novelGroups.forEach(g=>{if(g.country!=='Pendente'&&g.country!=='Não identificada'&&g.country!=='Conflito')nationalities.set(g.country,(nationalities.get(g.country)||0)+1)});
$('nationality').innerHTML+=([...nationalities].sort((a,b)=>a[0].localeCompare(b[0],'pt-BR')).map(([country,count])=>
  '<option value="'+esc(country)+'">'+esc(country)+' ('+fmt(count)+' novels)</option>').join(''));

function filterRecords(){
  const q=$('search').value.trim().toLocaleLowerCase();
  const n=$('nationality').value;
  filtered=novelGroups.filter(g=>
    (!q||[g.title,...(g.alternateTitles||[]),g.author,g.country,g.protagonists,...g.records.flatMap(r=>[r.obra_verificada,r.catalogo,r.titulo,r.nome])]
      .some(v=>String(v).toLocaleLowerCase().includes(q)))&&
    (!n||(n==='__nao_identificado__'
      ? ['pendente','não identificada','nao identificada','conflito'].includes(g.country.toLocaleLowerCase())
      : g.country===n))
  );
  page=0;render();
}
function referenceLinks(urls){
  return (urls||[]).length?urls.map((url,index)=>
    '<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+
    ((urls.length>1)?'Abrir '+(index+1):'Abrir')+'</a>').join(' · '):'—';
}
function duplicateDetailsMarkup(groups,record){
  const reference=record.fonte_nacionalidade_obra||record.referencia_obra||'';
  const entries=[{
    titulo:record.obra_verificada||record.titulo||record.nome||'EPUB selecionado',
    ids:[record.id||'—'],
    pais:record.nacionalidade_obra||'Pendente',
    identificado:record.localizada_em||'Pendente',
    referencias:reference?[reference]:[]
  }];
  const ownKey=String(record.obra_chave||'');
  (groups||[]).forEach(group=>(group.membros||[]).forEach(member=>{
    if(ownKey&&String(member.chave)===ownKey)return;
    entries.push({titulo:member.titulo||'Obra sem título',
    ids:member.ids||[],
    pais:member.pais||'Pendente',
    identificado:member.pais_identificado_em||'Pendente',
    referencias:member.referencias||[]
    });
  }));
  const rows=entries.map(entry=>'<tr><td>'+esc(entry.titulo)+'</td><td>'+
    esc((entry.ids||[]).join(', ')||'—')+'</td><td>'+esc(countryName(entry.pais))+
    '</td><td>'+esc(entry.identificado)+'</td><td>'+referenceLinks(entry.referencias)+
    '</td></tr>').join('');
  const groupsLabel=(groups||[]).length?((groups||[]).length+' grupo(s) de duplicatas relacionado(s)'):'Dados deste EPUB';
  return '<div class="detail-content"><p class="detail-heading">'+esc(groupsLabel)+
    '</p><div class="detail-table-wrap"><table class="detail-table"><thead><tr>'+
    '<th>Obra / registro relacionado</th><th>ID(s)</th><th>Origem</th>'+
    '<th>Fonte da origem</th><th>Referência</th></tr></thead><tbody>'+rows+
    '</tbody></table></div></div>';
}
function novelEpupsMarkup(g){
  const rows=g.records.map(r=>{const sourceTitle=r.obra_verificada||r.catalogo||r.titulo||'';return '<tr><td>'+((sourceTitle&&groupNorm(sourceTitle)!==groupNorm(g.title))?'<strong>'+esc(sourceTitle)+'</strong><br>':'')+esc(r.nome||'—')+'</td><td>'+esc(r.id||'—')+'</td><td>'+esc(countryName(r.nacionalidade_obra||'Pendente'))+'</td><td>'+esc(r.localizada_em||'Pendente')+'</td><td>'+referenceLinks(r.referencia_obra?[r.referencia_obra]:[] )+'</td></tr>'}).join('');
  return '<div class="detail-content"><p class="detail-heading">'+fmt(g.records.length)+' EPUB(s) associados a esta novel</p><div class="detail-table-wrap"><table class="detail-table"><thead><tr><th>Arquivo EPUB</th><th>ID</th><th>Origem</th><th>Fonte da origem</th><th>Referência</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>';
}
function toggleExplorerDetails(button){
  const row=$(button.getAttribute('aria-controls'));
  const expanded=button.getAttribute('aria-expanded')==='true';
  button.setAttribute('aria-expanded',String(!expanded));
  row.hidden=expanded;
}
function render(){
  const start=page*pageSize;
  const rows=filtered.slice(start,start+pageSize);
  $('tbody').innerHTML=rows.map((g,index)=>{
    const detailId='explorer-detail-'+page+'-'+index;
    return '<tr class="data-row"><td><div class="explorer-book"><strong>'+esc(g.title)+'</strong></div></td><td>'+esc(g.author)+
      '</td><td>'+esc(g.country)+
      '</td><td>'+esc(g.protagonists)+
      '</td><td>'+esc(g.verified)+'</td><td>'+fmt(g.records.length)+'</td><td class="explorer-expand-cell"><button type="button" class="row-expander" aria-label="Expandir EPUBs desta novel" title="Expandir EPUBs desta novel" aria-expanded="false" aria-controls="'+detailId+'" onclick="toggleExplorerDetails(this)"><span class="chevron" aria-hidden="true">›</span></button></td></tr>'+
      '<tr id="'+detailId+'" class="detail-row" hidden><td colspan="7">'+
      novelEpupsMarkup(g)+'</td></tr>';
  }).join('')||'<tr><td colspan="7">Nenhum resultado</td></tr>';
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
  if(m)return m[3]+'/'+m[2]+'/'+m[1]+(m[4]?' '+m[4]+':'+m[5]+':'+m[6]:'');
  return String(value);
}
function exportCSV(){
  const cols=['nome','titulo','autor','idioma','pais','origem_exibida',
    'obra_verificada','autor_obra','nacionalidade_obra','protagonistas_obra',
    'verificadas','localizada_em','fonte_nacionalidade_obra','referencia_obra','catalogo','id','data'];
  const quote=v=>'"'+String(Array.isArray(v)?v.join(' / '):(v??'')).replace(/"/g,'""')+'"';
  const csv='\ufeff'+[
    cols.join(';'),
    ...filtered.flatMap(g=>g.records).map(r=>cols.map(c=>quote(c==='origem_exibida'?countryName(r.nacionalidade_obra||r.pais):r[c])).join(';'))
  ].join('\r\n');
  const url=URL.createObjectURL(
    new Blob([csv],{type:'text/csv;charset=utf-8'})
  );
  const a=document.createElement('a');
  a.href=url;a.download='epubs_filtrados.csv';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
navigate(['overview','novels'].includes(location.hash.slice(1))?location.hash.slice(1):'overview');
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

import csv
import re
import unicodedata
from pathlib import Path
from collections import defaultdict
from rapidfuzz import fuzz

BASE = Path("/Users/alinesouza/Documents/TI/Projetos/Extract_txt")
ENTRADA = BASE / "output/telegram_midias_apenas_epub_origens_v3_ptbr.csv"
SAIDA = BASE / "output"

def normalizar(valor):
    valor = unicodedata.normalize("NFKC", valor or "")
    valor = valor.casefold()
    valor = "".join(
        c for c in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(c)
    )
    valor = re.sub(r"\.(epub|mobi|pdf|txt)$", "", valor)
    valor = re.sub(r"[_\-]+", " ", valor)
    valor = re.sub(r"[^\w\s]", " ", valor)
    valor = re.sub(r"\s+", " ", valor)
    return valor.strip()

def titulo_da_linha(linha):
    return (
        (linha.get("titulo_catalogo") or "").strip()
        or (linha.get("titulo_normalizado") or "").strip()
        or Path(linha.get("nome_arquivo") or "").stem
    )

# Ler registros
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    registros = list(csv.DictReader(f, delimiter=";"))

# Consolidar EPUBs com mesmo título e autor
obras = {}

for linha in registros:
    titulo = titulo_da_linha(linha)
    autor = (linha.get("autor_catalogo") or "").strip()
    chave = (normalizar(titulo), normalizar(autor))

    if not chave[0]:
        continue

    if chave not in obras:
        obras[chave] = {
            "titulo": titulo,
            "autor": autor,
            "normalizado": chave[0],
            "autor_norm": chave[1],
            "ids": [],
            "quantidade": 0,
        }

    obras[chave]["quantidade"] += 1
    obras[chave]["ids"].append(linha.get("id_mensagem") or "")

lista = list(obras.values())
pares = []

# Comparação entre títulos distintos
for i, a in enumerate(lista):
    for b in lista[i + 1:]:
        if a["normalizado"] == b["normalizado"]:
            score = 100.0
        else:
            score = fuzz.WRatio(
                a["normalizado"], b["normalizado"]
            )

        mesmo_autor = bool(
            a["autor_norm"]
            and a["autor_norm"] == b["autor_norm"]
        )

        autores_diferentes = bool(
            a["autor_norm"]
            and b["autor_norm"]
            and a["autor_norm"] != b["autor_norm"]
        )

        if autores_diferentes:
            continue

        if score >= 95 and (mesmo_autor or a["normalizado"] == b["normalizado"]):
            status = "ALTA_CONFIANCA"
        elif score >= 85:
            status = "REVISAR"
        elif score >= 75 and mesmo_autor:
            status = "REVISAR"
        else:
            continue

        pares.append({
            "status": status,
            "similaridade": round(score, 2),
            "obra_1": a["titulo"],
            "obra_2": b["titulo"],
            "autor_1": a["autor"],
            "autor_2": b["autor"],
            "qtd_epubs_1": a["quantidade"],
            "qtd_epubs_2": b["quantidade"],
            "ids_mensagem_1": ",".join(a["ids"]),
            "ids_mensagem_2": ",".join(b["ids"]),
        })

pares.sort(
    key=lambda x: (
        x["status"] != "ALTA_CONFIANCA",
        -x["similaridade"],
    )
)

arquivo = SAIDA / "obras_duplicadas_candidatas.csv"

campos = [
    "status", "similaridade",
    "obra_1", "obra_2",
    "autor_1", "autor_2",
    "qtd_epubs_1", "qtd_epubs_2",
    "ids_mensagem_1", "ids_mensagem_2",
]

with arquivo.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    writer.writeheader()
    writer.writerows(pares)

alta = sum(p["status"] == "ALTA_CONFIANCA" for p in pares)

print("\n=== RELATÓRIO DE DUPLICATAS ===")
print(f"EPUBs analisados: {len(registros)}")
print(f"Títulos/autor distintos: {len(lista)}")
print(f"Pares candidatos: {len(pares)}")
print(f"Alta confiança: {alta}")
print(f"Para revisão: {len(pares) - alta}")
print(f"\nRelatório: {arquivo}")
print("\n=== PRIMEIROS 20 PARES ===")

for p in pares[:20]:
    print(
        f"\n[{p['status']}] {p['similaridade']}%"
        f"\n  {p['obra_1']}"
        f"\n  {p['obra_2']}"
        f"\n  Autor: {p['autor_1'] or p['autor_2'] or 'Não identificado'}"
    )

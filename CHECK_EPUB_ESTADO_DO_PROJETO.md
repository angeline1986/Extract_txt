# Check EPUB — estado consolidado

Atualizado: 2026-11-17 22:04

## Objetivo e sequência

1. Inventariar downloads locais e metadados EPUB (OPF e links XHTML).
2. Agrupar cópias com evidência forte: SHA-256, identificadores NovelUpdates/JJWXC ou título+autor iguais.
3. Preservar homônimos, edições e volumes ambíguos para cruzamento posterior.
4. Somente depois pesquisar na Serper os casos ainda sem referência suficiente.

## Entradas e saídas

- Catálogo principal (somente leitura): `output/telegram_midias_apenas_epub_origens_v3_ptbr.csv` (5118 registros).
- Candidatos anteriores (somente leitura): `novelupdates_candidatos.json` (20 registros).
- Varredura local: `output/check_epub_varredura.json` (3730 arquivos).
- Agrupamentos e evidências: `output/check_epub_obras.json` (3030 grupos).
- Painel offline: `output/relatorio_telegram.html`.
- Backup do painel: `output/relatorio_telegram.html.bak_check_epub`.

## Resumo desta execução

- EPUBs locais varridos: **3730**.
- Agrupamentos conservadores: **3030**.
- Grupos de duplicatas com evidência (EPUBs baixados): **427**.
- Grupos de possíveis duplicatas entre os já identificados no catálogo (título+autor): **95**.
- Grupos baixados sem identificação confirmada (inclusive com URL NU ainda não validada): **3030**.
- Problemas comprovadamente sem solução: **não apurados**; requer histórico completo das ações e alternativas.
- EPUBs com falha de leitura: **1**.

## Regras e limitações

- Um link interno é evidência/candidato, não confirmação definitiva de identidade.
- A falta de um link não prova que a obra não existe no NovelUpdates.
- Duplicação de título sem autor ou identificador não prova duplicação de obra.
- A classificação 'problemas sem solução' exige histórico de tentativas e alternativas, não inferível apenas do CSV.
- Nenhum EPUB, catálogo ou manifesto de downloads é alterado.
- A varredura só cobre os EPUBs existentes na pasta indicada por `--epubs`.

## Execução

```bash
cd ~/Documents/TI/Projetos/Extract_txt
python3 ~/Downloads/check_epub_consolidar.py --projeto . --epubs /Volumes/Seagate2T/old/Check_Epub
```

## Pendências

- Verificar a cobertura da pasta de downloads e os resultados do agrupamento.
- Cruzar posteriormente metadados internos com candidatos do NovelUpdates.
- Integrar o histórico das ações anteriores para comprovar falhas irrecuperáveis.

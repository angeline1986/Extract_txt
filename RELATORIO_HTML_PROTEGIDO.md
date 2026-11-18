# Relatório HTML protegido

O painel `output/relatorio_telegram.html` contém correções manuais que os geradores
atuais não reproduzem. Os três scripts que escrevem nesse painel verificam a
existência deste arquivo antes de iniciar qualquer alteração e interrompem a
execução para evitar rollback:

- `scripts/gerar_relatorio_telegram.py`
- `scripts/check_epub_consolidar.py`
- `scripts/check_epub_oficial.py`

Não execute esses scripts nem remova esta proteção durante a revisão atual.
Antes de uma futura geração, incorpore todas as correções às fontes de dados e
ao código gerador, confira a diferença com o painel atual e mantenha um backup.

O painel ativo voltou a ser um único arquivo: `output/relatorio_telegram.html`.
Os dados de Novels estão incorporados em texto legível; os dados extensos das
abas de conferência estão incorporados em formato compactado e só são
descompactados ao abrir uma dessas abas. Assim, o endereço `file://` não depende
de arquivos JavaScript vizinhos.

Os arquivos `output/relatorio_telegram_data.js`,
`output/relatorio_telegram_ce_data.js` e `output/relatorio_telegram_ce_ui.js`
são cópias de referência da extração. Alterá-los isoladamente não altera o
painel aberto no navegador.

Em 17/11/2026, o mapa exato `input/autores_de_para.json` foi aplicado aos
campos de autoria do HTML e de `output/check_epub_obras.json`. O arquivo
`output/autores.json` já tinha suas 1.701 entradas de autor padronizadas.
Backup da fonte antes dessa aplicação:
`output/check_epub_obras.json.bak_antes_mapa_autores_20261117`.

`output/` é ignorado pelo Git. Para preservar uma cópia recuperável fora dessa
pasta, o arquivo `relatorio_telegram_snapshot_20261117.tar.gz` contém o HTML
atual completo. Há também uma cópia exata do HTML anterior à otimização em
`output/relatorio_telegram.html.bak_20261117_antes_otimizacao`.

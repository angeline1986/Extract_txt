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

Em 17/11/2026, começou o reagrupamento por nacionalidade na aba "EPUBs por
novel". China, Coreia do Sul e Estados Unidos usam a regra de mesmo autor e
mesmo título após remover apenas um marcador explícito de volume (Book, Vol.,
Part etc.). Na China, isso inclui "Learning God Is In Hand" e "A Bystander, But
Pregnant with the Evil God’s Child". Três arquivos com o título truncado
"The Scum Villain’s Self-1" foram vinculados especificamente à obra principal;
"BingJiu" permanece separado. Na Coreia do Sul, variantes confirmadas de
"Codename Anastasia" e os volumes/edições de "Under the Oak Tree" também são
reunidos; "Under the Oak Tree: Season 1 (Side Story)" permanece separado.
As demais nacionalidades ainda não passaram por esta etapa. A regra também
foi incorporada ao código gerador, mas o bloqueio de execução dos scripts
continua ativo.

O registro `obra_00116` (EPUB `18037`) exibe agora
`The Last Gentleman (终末的绅士)` no lugar do identificador hexadecimal. O título
foi corrigido também nas duas entradas de `output/check_epub_obras.json`.
O registro `obra_00705` (EPUB `39550`) exibe `Bat (蝙蝠)` no lugar do nome
derivado do arquivo `39550_-.epub`; a fonte de conferência e o mapeamento de
apresentação do consolidador foram alinhados com esse título.
O registro `obra_00842` (EPUB `45712`) exibe `Desire (垂涎)` no lugar do
identificador hexadecimal. As chaves `obra_00842`, `obra_00898` e
`obra_02641` são reunidas em uma linha por serem a mesma obra; `ABO Desire`
foi mantido como título alternativo de busca.
O registro `obra_00044` (EPUB `12653`) exibe
`To Rule in a Turbulent World (乱世为王)` no lugar do identificador hexadecimal.
Seis chaves da obra, incluindo os volumes espanhóis de `obra_01705`, são
reunidas em uma linha. A tabela mostra a autoria canônica
`Fei Tian Ye Xiang (非天夜翔)`; os dados de verificação preservam o crédito
original `Gu Xue Rou (顾雪柔)`, pseudônimo usado na publicação.

Em 18/11/2026, a revisão da China passou a considerar autor e referência
específica da obra (página de série do Novel Updates ou ID de obra do JJWXC)
além do título. A obra `I Became a God in a Horror Game` reúne 23 EPUBs
de 13 chaves, inclusive Extras, o capítulo #589 e versões em espanhol/chinês.
Famílias com fontes ou traduções diferentes foram conferidas por autor,
personagens e título: `The King's Avatar`, `S.C.I Mystery Series`,
`After Rebirth, The Real Young Master Began to Maintain His Health`,
`Little Mushroom`, `The Wife Comes First`, `The Legendary Master's Wife`,
`The Easter Egg Game / The Lucky Egg Game`, `Kaleidoscope of Death`,
`Golden Terrace / Golden Stage` e `There's Something Wrong with the Chief`.
O especial `2022 Zhongyuan Mini-Theatre` permanece separado de `Yin Ke`.
Essas regras estão no HTML e no gerador, sem remover a proteção contra
execução dos scripts.

Os títulos de exibição `0 and 1 (0과 1)` e `Case File Compendium (Bing An Ben)`
foram corrigidos nos registros correspondentes. O ID `7106` do catálogo
`input/novels_0.1.5.csv` designa `When I Met You`; o EPUB ID `7106`
pertence a `Case File Compendium`. São identificadores de fontes diferentes.

Ainda em 18/11/2026, a varredura por autor ampliou o mapa de famílias chinesas
revisadas para 74 famílias e 261 chaves (436 EPUBs no inventário antes do filtro
de disponibilidade local). As correspondências
incluem `Bat / The Story of the Bat`, a edição russa de `Thousand Autumns`,
`Hidden Love / Secretly, Secretly But Unable to Hide It`,
`The Husky and His White Cat Shizun`, `Art Thou Ailing? / Jun You Ji Fou`,
`Rose and Renaissance / I Only Like Your Character Settings`,
`Silent Reading / Entre líneas`, `Paper Plane / Paper Airplane` e outros
pares confirmados por autor, protagonistas e título ou referência. O mapa
explícito do HTML corresponde ao do gerador. O consolidador trata a franquia
`Daomu Biji` em uma regra própria, com suas obras internas identificadas.

Permanecem fora da união automática séries e sequências com identidade
incerta ou distinta, especialmente `Living to Suffer` e
`Till Death Us Do Part`, as demais obras da franquia `Daomu Biji`, e
`After the Full-Level Boss Entered the Infinite Game` versus
`The Return of the Lord God`. É necessária revisão individual antes de
reunir essas chaves. A existência deste arquivo continua bloqueando a
execução dos scripts do projeto.

Na continuação da revisão em 18/11/2026, 18 IDs de EPUB chineses sem
`obra_chave` foram associados diretamente a chaves já conferidas. Isso
inclui `Wu Chang Jie`, `Welcome to the Nightmare Live`, `Silent Reading`,
`I Ship My Adversary X Me` e `The White Cat's Divine Scratching Post`.
O agrupamento por alias de título na China passou a exigir o mesmo autor.
Antes dessa correção, o EPUB `42588` podia ser associado à obra de outro
autor e o EPUB `16349` à obra inglesa de Kim Jin.

`The Grave Robbers’ Chronicles` e `Daomu Biji` foram reunidos como a
série principal. `The Mystic Nine` e suas edições/Extras foram reunidos
em outra linha, pois são um prelúdio distinto. O EPUB `83027`, chamado
`To Be or Not Be`, aponta para a página da novel `How to Survive as a
Villain` e foi incluído nessa obra. `Criminal Investigation Files`
(EPUB `72836`) permanece separado de `Criminal Investigation Notes`:
o catálogo Novel Updates os trata como obras diferentes do mesmo autor.

Outra rodada por autor reuniu edições de `The Marquis Is Innocent`,
`The Imperial Uncle`, `The Rebirth of the General Who Always Sees Himself
as a Replacement`, `Jianghu Demolition Squad`, `Till Death Do Us Part`,
`My Husband and I Sleep in a Coffin`, `The Blind Concubine` e outras
famílias com título equivalente e mesmo autor. `Till Death Do Us Part`
continua separado da obra anterior `Living to Suffer`.
O EPUB `22006` de `The Imperial Uncle` tinha um protagonista incorreto;
os dados do HTML, a fonte `output/check_epub_obras.json` e a correção
manual do consolidador agora apontam para Cheng Jun (Prince Huai) e
Liu Tongyi. A linha de `The Mystic Nine` não exibe os protagonistas
atribuídos à série principal, pois essa identificação ainda requer revisão.

O EPUB `81635` (antes `1.1 Anthology`) e o EPUB `80232` (antes com título
derivado do nome do arquivo) pertencem a
`[Quick Transmigration] The Delicate Little Beauty Keeps Getting Caught`,
de Shi Yu (是玉), e aparecem em uma linha com 2 EPUBs.
O título original `【快穿】总被抓的美貌小可怜` foi guardado como alternativa
de busca. O HTML, as quatro entradas duplicadas de `output/check_epub_obras.json`,
o resumo local `output/autores.json` e a correção manual no consolidador
foram alinhados. O ID `81635` no catálogo `input/novels_0.1.5.csv`
identifica outra obra coreana; não foi usado para nomear este EPUB.

Em 18/11/2026, os 5.118 IDs do inventário Telegram foram cruzados com os
arquivos da pasta `/Volumes/Seagate2T/old/Check_Epub`. A correspondência exige
o ID da mensagem no prefixo do nome do arquivo e o mesmo tamanho em bytes;
arquivos auxiliares `._` do macOS foram ignorados. Foram confirmados 3.730
EPUBs locais e identificadas 1.388 mensagens sem arquivo nessa pasta. O
resultado completo está em `output/auditoria_epubs_locais_20261118.csv`,
a lista somente dos ausentes em `output/epubs_sem_arquivo_local_20261118.csv`, e
`input/epubs_locais_confirmados_20261118.json` guarda os IDs confirmados.
Todas as abas do HTML agora usam somente os 3.730 EPUBs confirmados; os 1.388
ausentes foram removidos dos dados embutidos e das duplicatas de catálogo
compactadas. A visão geral recalcula seus contadores a partir desse conjunto.
Os CSVs originais ficaram intactos. Uma cópia do HTML anterior à remoção,
com as correções manuais já existentes, está em
`output/relatorio_telegram_inventario_completo_antes_filtro_20261118.html`;
o arquivo `relatorio_telegram_inventario_completo_antes_filtro_20261118.tar.gz`
preserva a mesma cópia fora de `output/`.
O manifesto é uma fotografia dessa pasta nessa data; deve ser refeito se os
arquivos locais forem alterados antes de uma futura geração do painel.

Em 19/11/2026, a coluna de apresentação passou a se chamar `Origem`.
Os registros já classificados como `Não identificada (obra original em inglês)`
aparecem como `Internacional (OEL — inglês)`; os classificados como
`Não identificada (fanfic em inglês)` aparecem como `Fanfic (inglês)`.
Isso inclui `A Gorgeous White (BL)` (EPUB `49677`) e as fanfics indicadas
nos dados de conferência. A mudança é de apresentação: a nacionalidade da
autora e o país de criação continuam não confirmados nos campos de origem.
O mapeamento foi preservado no gerador e nas interfaces auxiliares; os scripts
permanecem bloqueados por este arquivo.

Ainda em 19/11/2026, foram conferidos os nove títulos OEL/fanfic informados
pela usuária. Seus registros já continham a distinção entre obra original em
inglês e fanfic em inglês, exibida pela regra acima. Os EPUBs `86187` e
`86083` de `Let This F-Class Guide Live in Peace!`, com as chaves
`obra_02108` e `obra_02103`, agora formam uma linha de 2 EPUBs na aba por
novel. A correspondência exata também foi incluída no gerador e no
consolidador, mantendo os dois IDs individuais nas linhas expandidas.
O resumo local `output/autores.json` registra Delana com uma obra e dois EPUBs.

Em 19/11/2026, a seção Cherrymist da Visão geral foi conferida contra as
712 entradas (710 títulos distintos) de
`input/cherry_mist_obras_catalogo_completo.txt`, cópia da listagem fornecida
pela usuária. O primeiro cruzamento com os 3.730 EPUBs locais confirmados
apontou 8 candidatos por título ou alias: `Binding Flower` (ID 89102),
`Eunuch`/`Hwan` (93710),
`Fated Calamity`/`An Eon in a Name` (85331),
`Hell Execution Order`/`Hell Execution Command` (89272),
`Leveling Up in the Grand Duke’s Bed` (88188), `Lumen Project` (80402),
`Reap What You Sow` (74491) e
`The Island Where the Hunter Sleeps`/`The Island Where the Seeker Sleeps`
(83358). Esse primeiro critério não comprovava a origem da edição local;
a revisão posterior está registrada abaixo.

Ainda em 19/11/2026, os botões das abas "Explorador de EPUBs" e "Obras"
foram retirados do HTML ativo. A navegação aceita apenas "Visão geral" e
"EPUBs por novel", inclusive ao abrir uma URL com fragmento antigo. A
renderização inicial da tabela do Explorador foi desativada. As fontes do
gerador e do consolidador foram alinhadas para não recriar esses botões em
uma futura geração; a proteção contra execução dos scripts continua ativa.

O cartão "Grupos por novel" foi retirado da Visão geral no HTML ativo e no
modelo do gerador. Os demais indicadores e os dados embutidos foram mantidos.

Após questionamento da usuária, a seção Cherrymist foi corrigida para exigir
evidência direta no EPUB local, além da identidade da obra no catálogo. Restam
3 EPUBs: `Binding Flower` (89102, link da página Cherry Mist),
`Hell Execution Command` (89272, links de capítulos Cherry Mist) e
`Lumen Project` (80402, página e capítulos Cherry Mist). A associação agora
usa ID de EPUB, para não incluir automaticamente outra edição da mesma obra.
O quadro mostra a URL da evidência extraída de cada arquivo.

Os outros 5 candidatos foram retirados: `Eunuch` (93710) é uma edição ESP
com link para outro site; `Fated Calamity`/`An Eon in a Name` (85331) não
tem fonte Cherry Mist comprovada no arquivo; `Leveling Up in the Grand Duke’s
Bed` (88188) contém links de `praise-yaoi.blogspot.com`; `The Island Where
the Hunter Sleeps` (83358) contém capítulos de `maplesantl.com`; e o
`Reap What You Sow` do grupo é uma obra coreana de Mun Mujin, enquanto o
EPUB 74491 é a obra chinesa homônima de Bai Jiezi. A auditoria por entrada
foi atualizada em `output/cherrymist_auditoria_20261119.csv`. O HTML e o
gerador foram alinhados sem executar scripts do projeto.

Em nova conferência de 21 títulos informados pela usuária, 11 aparecem na
listagem Cherrymist anexada e 2 têm EPUB local: `Hell Execution Order`
(EPUB 89272, exibido como `Hell Execution Command`) e
`Almost, But Not Quite` (EPUB 74000). Este último não está na listagem
anexada, mas o Novel Updates registra lançamentos do grupo e o EPUB contém
links para capítulos em `cherrymist.cafe`; foi incluído na seção Cherrymist.
O resultado completo está em
`output/cherrymist_titulos_solicitados_20261119.csv`. A seção agora reúne
4 EPUBs locais com evidência direta do site do grupo. Nacionalidades
informadas na nova lista não foram aplicadas sem conferência.

Na Tailândia, os EPUBs idênticos 14557 e 61897, antes exibidos pelo hash
`1393b2b0b2e3c0c9558ae1a3715116bb`, receberam o título
`VegasPete (KinnPorsche Side Story)`, protagonistas Vegas e Pete e autor
`Não identificado`. O conteúdo e os links do arquivo sustentam o título;
o metadado de criador contém somente um e-mail. A autoria de DAEMI para
`KinnPorsche` e a de Tiara ME para outra obra de VegasPete não foram
atribuídas automaticamente a esta cópia. O HTML, `output/check_epub_obras.json`,
`output/autores.json` e a regra de apresentação do consolidador foram
alinhados. Os CSVs originais permaneceram intactos; nenhum script do projeto
foi executado.

Após a tentativa de compartilhar o HTML pelo Telegram, o aviso da Visão geral
sobre a conferência por ID e tamanho em 18/11/2026 foi retirado do painel
ativo e do gerador. O HTML interativo preenche as tabelas com JavaScript;
visualizadores que não executam esse código podem mostrar a página vazia.
Foi criada `output/relatorio_telegram_para_compartilhar.html` a partir do
painel ativo. Essa cópia preserva o layout, as duas abas, a busca, os filtros
e a paginação quando aberta em um navegador com JavaScript. Para prévias que
não executam JavaScript, inclui no próprio HTML uma tabela já preenchida com
os 3.730 EPUBs e a seção Cherry Mist. Nesse modo, a busca disponível é a do
visualizador/navegador; os controles interativos dependem de JavaScript.
Os dados compactados das abas de conferência, que não estão na navegação,
foram omitidos somente da cópia de compartilhamento para reduzir o tamanho.
Essa cópia é um retrato do acervo nesta data: depois de futuras alterações no
painel, será preciso atualizá-la antes de compartilhar novamente. Nenhum
script do projeto foi executado para criá-la.

Os EPUBs 83728 e 83730 (`obra_01947`), cópias idênticas com nome de arquivo
`4_6008075621178023763.epub`, passaram a exibir `Even Better` em vez do
identificador numérico. O MebMarket e o registro original de Dek-D identificam
a obra de peachhplease; o conteúdo dos EPUBs corresponde à história de
Jettana (Jamie) e Marvis (Mars). A correção foi aplicada aos dois registros
do HTML, a `output/check_epub_obras.json`, a `output/autores.json`, à versão
para compartilhar e às regras de apresentação do gerador e do
consolidador. Os nomes físicos dos EPUBs e os CSVs originais não foram alterados.

Em 20/11/2026, títulos tailandeses exibidos incorretamente foram corrigidos
pelos IDs de EPUB: `Heartbound` (84060, 83243), `Crazy Love Moo Moo` (75911),
`NITI man, society and lover` (66740, 58718), `Cutie Pie` (5850, 5857),
`Space: The Gap Between Us` (55509) e `My Only 12%` (1965, 1568).
`Cranium` (81494) já estava correto. As duas entradas de Heartbound, Cutie
Pie e NITI man foram reunidas em uma linha por obra no painel. Os títulos
foram alinhados no HTML ativo, na cópia para compartilhar, em
`output/check_epub_obras.json`, em `output/autores.json` e nas regras de
apresentação dos dois geradores. Backups com sufixo
`.bak_20261120_antes_nomes_tailandia` foram preservados em `output/`.
Os nomes físicos dos EPUBs e os CSVs originais permaneceram intactos; nenhum
script do projeto foi executado.

Ainda em 20/11/2026, foi corrigida uma colisão no agrupamento de `Look at Me`.
O EPUB 75106 é a obra chinesa `Why Do All My Roommates Look at Me Like This?`,
de Gong Zi Yu Ge; os EPUBs 59957, 59943, 59940, 59867 e 59865 são a obra
coreana `Look at Me`, de Tansan. A regra de série passou a exigir que o título
comece por `Look at Me`, evitando a junção pelo trecho intermediário do título
chinês. As duas linhas foram separadas no HTML ativo e na planilha; a cópia
para compartilhar, `output/check_epub_obras.json`, `output/autores.json` e as
regras dos geradores foram alinhadas. O índice da planilha passa a contar
2.429 títulos e 3.686 EPUBs com origem classificada. Backups com sufixo
`.bak_20261120_antes_separar_look_at_me` foram guardados em `output/`.
Nenhum script do projeto foi executado.

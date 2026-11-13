#!/usr/bin/env python3
import csv, collections, datetime, pathlib, unicodedata
ROOT=pathlib.Path(__file__).resolve().parent.parent if pathlib.Path(__file__).resolve().parent.name=='scripts' else pathlib.Path.cwd()
INV=ROOT/'input/telegram_midias_20261111_093138.csv'
CLS=ROOT/'output/telegram_midias_apenas_epub_origens_v3_ptbr.csv'
OUT=ROOT/'output/relatorio_telegram.txt'

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        sample=f.read(32768);f.seek(0)
        try: delim=csv.Sniffer().sniff(sample,delimiters=',;').delimiter
        except csv.Error: delim=';' if sample.splitlines()[0].count(';')>sample.splitlines()[0].count(',') else ','
        reader=csv.DictReader(f,delimiter=delim)
        rows=list(reader)
        return rows,reader.fieldnames or [],delim

def val(row,*names):
    for name in names:
        if name in row and row[name] is not None:return str(row[name]).strip()
    return ''

def norm(s):
    return ' '.join(unicodedata.normalize('NFKC',s).casefold().replace('_',' ').split())

def main():
    inv,ih,di=read(INV);cls,ch,dc=read(CLS)
    required=['nome_arquivo','tipo']
    if any(k not in ih for k in required):raise SystemExit(f'Colunas de inventario inesperadas: {ih}')
    if 'nome_arquivo' not in ch:raise SystemExit(f'Colunas de classificacao inesperadas: {ch}')
    statuses=collections.Counter(); origins=collections.Counter(); keys=set(); identified_keys=set(); exact=review=missing=other=0
    for r in cls:
        st=norm(val(r,'status_verificacao','status','tipo_correspondencia'))
        country=val(r,'pais_origem','origem','original_language','idioma_original')
        statuses[st or '(vazio)']+=1
        title=norm(val(r,'titulo_normalizado') or val(r,'nome_arquivo'))
        keys.add(title)
        if 'correspondencia_exata' in st or st in ('exato','exact','exact_match'):
            exact+=1
            if country and country.upper() not in ('INDEFINIDO','UNKNOWN','N/A','-'):
                identified_keys.add(title);origins[country]+=1
        elif 'revisar' in st or 'aproximad' in st or 'fuzzy' in st:review+=1
        elif 'nao_encontrado' in st or 'não encontrado' in st or 'not_found' in st:missing+=1
        else:other+=1
    docs_epub=docs_other=photos=videos=others=0
    for r in inv:
        typ=norm(val(r,'tipo')); name=val(r,'nome_arquivo').lower()
        if typ=='foto':photos+=1
        elif typ=='documento':
            if name.endswith('.epub'):docs_epub+=1
            else:docs_other+=1
        elif typ in ('video','vídeo','animacao','animação','video_note'):videos+=1
        else:others+=1
    lines=[
      'RELATORIO DE INVENTARIO E CLASSIFICACAO - TELEGRAM', '='*65,
      'Gerado em: '+datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
      'Inventario: '+str(INV),'Classificacao: '+str(CLS),
      f'Separadores detectados: inventario={di!r}; classificacao={dc!r}',
      '', '1. INVENTARIO GERAL', '-'*65,
      f'Total de registros de midia: {len(inv)}',f'Imagens/fotos: {photos}',
      f'Documentos EPUB: {docs_epub}',f'Documentos nao EPUB: {docs_other}',
      f'Videos/animacoes: {videos}',f'Outros tipos: {others}',
      f'Conferencia: {photos+docs_epub+docs_other+videos+others}',
      '', '2. CLASSIFICACAO DOS EPUBS', '-'*65,
      f'Linhas no CSV classificado: {len(cls)}',f'Correspondencias exatas: {exact}',
      f'Exatas com origem preenchida: {sum(origins.values())}',
      f'Correspondencias para revisar: {review}',f'Nao encontrados: {missing}',
      f'Outros status: {other}',f'Titulos normalizados distintos: {len(keys)}',
      f'Titulos distintos com correspondencia exata e origem: {len(identified_keys)}',
      '', '3. DISTRIBUICAO DE ORIGENS NAS CORRESPONDENCIAS EXATAS', '-'*65,
      *[f'{k}: {v}' for k,v in origins.most_common()],
      '', '4. CHERRYMIST', '-'*65,
      'Nao verificado: requer catalogo de referencia confiavel das obras Cherrymist.',
      '', '5. AUDITORIA', '-'*65,
      f'Diferenca de linhas EPUB (classificacao - inventario): {len(cls)-docs_epub}',
      'Status observados: '+repr(dict(statuses)),
      'Contagens por arquivo/mensagem, podendo incluir duplicatas.',
      'Idioma original catalogado nao comprova nacionalidade do autor.'
    ]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    print('\nRelatorio salvo:',OUT)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Check Epub: downloader com pausas, retomada e respeito a FloodWait."""
import argparse
import asyncio
import csv
import json
import os
import random
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError

ROOT = Path(__file__).resolve().parent.parent
DEST = Path('/Volumes/Seagate2T/old/Check_Epub')
CSV_PATH = ROOT / 'output/telegram_midias_apenas_epub_origens_v3_ptbr.csv'
MANIFEST = DEST / 'downloads_manifest.jsonl'
REPORT = ROOT / 'epubs_pendentes.txt'
CORRUPT_IDS = {27799, 26276}  # Auditoria: investigar depois; nunca alterar agora.



def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        header = f.readline()
        f.seek(0)
        sep = ';' if header.count(';') > header.count(',') else ','
        return list(csv.DictReader(f, delimiter=sep))


def classify(value):
    s = (value or '').strip().lower()
    if 'revis' in s or 'aproxim' in s:
        return 'revisar'
    if 'nao_encontr' in s or 'não_encontr' in s:
        return 'nao_encontrado'
    return None


def safe_name(name):
    name = Path((name or 'arquivo.epub').replace('\\', '/')).name
    name = re.sub(r'[\x00-\x1f/:*?"<>|]', '_', name)
    return name[:180] or 'arquivo.epub'


def load_completed():
    done = {}
    if not MANIFEST.exists():
        return done
    with MANIFEST.open(encoding='utf-8') as f:
        for line in f:
            try:
                item = json.loads(line)
                if item.get('status') == 'concluido':
                    done[item['key']] = item
            except (ValueError, KeyError):
                continue
    return done


def record_event(event):
    with MANIFEST.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')
        f.flush()


def build_jobs(rows):
    jobs, seen = [], set()
    for r in rows:
        status = classify(r.get('status_verificacao'))
        if status is None:
            continue
        try:
            mid = int(r.get('id_mensagem', ''))
            expected_size = int(r.get('tamanho_bytes') or 0)
        except (ValueError, TypeError):
            continue
        if mid in seen:
            continue
        seen.add(mid)
        jobs.append({
            'key': str(mid), 'id': mid, 'status': status,
            'name': safe_name(r.get('nome_arquivo')),
            'expected_size': expected_size,
        })
    # Processar os menores EPUBs primeiro; tamanho desconhecido fica no final.
    # Ordenação estável para tamanhos iguais (preserva a ordem original do CSV).
    jobs.sort(key=lambda job: (job["expected_size"] <= 0, job["expected_size"] if job["expected_size"] > 0 else 0))
    return jobs


def target_for(job):
    folder = DEST / ('Para_Revisao' if job['status'] == 'revisar' else 'Nao_Encontrados')
    name = f'{job["id"]}_{job["name"]}'
    if not name.lower().endswith('.epub'):
        name += '.epub'
    return folder / name


def pending_jobs(jobs, chat):
    """Seleciona pendências reais sem tocar nos EPUBs existentes."""
    completed = load_completed()
    chat_id = str(chat).removeprefix('-100')
    pending, excluded, complete, conflicts = [], [], 0, []
    for job in jobs:
        if job['id'] in CORRUPT_IDS:
            excluded.append(job)
            continue
        target = target_for(job)
        previous = completed.get(chat_id + ':' + job['key'])
        if previous and target.is_file() and target.stat().st_size == previous.get('bytes'):
            complete += 1
        elif target.exists() and not previous:
            conflicts.append(job)
        else:
            pending.append(job)
    return pending, excluded, complete, conflicts


def write_report(pending, excluded, complete, conflicts):
    lines = [
        'CHECK EPUB - RELATORIO DE DOWNLOADS PENDENTES',
        'Atualizado em: ' + datetime.now().isoformat(timespec='seconds'),
        'CSV de origem: ' + str(CSV_PATH),
        'Manifesto: ' + str(MANIFEST),
        'Arquivos concluidos e conferidos por tamanho: ' + str(complete),
        'Pendentes para download: ' + str(len(pending)),
        'Arquivos corrompidos excluidos temporariamente: ' + str(len(excluded)),
        'Arquivos existentes sem manifesto (revisao manual): ' + str(len(conflicts)),
        '',
        'PENDENTES (DO MENOR PARA O MAIOR)',
    ]
    for n, job in enumerate(pending, 1):
        mib = f"{job['expected_size'] / 1048576:.2f} MiB" if job['expected_size'] > 0 else 'desconhecido'
        lines.append(f"{n:04d} | ID {job['id']} | {mib} | {job['status']} | {job['name']}")
    lines.extend(['', 'EXCLUIDOS TEMPORARIAMENTE - NAO BAIXAR'])
    for job in excluded:
        lines.append(f"ID {job['id']} | {job['name']} | EPUB invalido na auditoria")
    lines.extend(['', 'EXISTENTES SEM REGISTRO DE CONCLUSAO - REVISAO MANUAL'])
    for job in conflicts:
        lines.append(f"ID {job['id']} | {job['name']} | {target_for(job)}")
    REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return REPORT


async def download(args, jobs):
    if not DEST.parent.is_dir():
        raise RuntimeError('HD externo não encontrado: ' + str(DEST.parent))
    if not args.chat:
        raise RuntimeError('Informe --chat com o grupo/canal original.')
    api_id = args.api_id or os.getenv('TELEGRAM_API_ID')
    api_hash = args.api_hash or os.getenv('TELEGRAM_API_HASH')
    if not api_id or not api_hash:
        raise RuntimeError('Configure TELEGRAM_API_ID e TELEGRAM_API_HASH.')

    DEST.mkdir(parents=True, exist_ok=True)
    completed = load_completed()
    client = TelegramClient(
        str(Path.home() / '.telegram_extrator_midias'), int(api_id), api_hash,
        flood_sleep_threshold=0,
    )
    await client.start()
    try:
        dialogs = [d async for d in client.iter_dialogs() if d.is_group or d.is_channel]
        dialog = next((d for d in dialogs if str(d.id) == str(args.chat)), None)
        if dialog is None:
            raise RuntimeError('Grupo não encontrado na sessão')
        entity = dialog.entity
        chat_id = str(entity.id)
        ok = skipped = failed = 0
        last_request = False
        for index, job in enumerate(jobs, 1):
            key = chat_id + ':' + job['key']
            target = target_for(job)
            previous = completed.get(key)
            if previous and target.is_file() and target.stat().st_size == previous.get('bytes'):
                skipped += 1
                continue
            # Não sobrescrever arquivos preexistentes que não constam do manifesto.
            if target.exists() and not previous:
                print(f'[{index}/{len(jobs)}] EXISTENTE sem manifesto, revisar: {target.name}', flush=True)
                failed += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + '.part')
            print(f'[{index}/{len(jobs)}] {target.name}', flush=True)
            attempts = 0
            while True:
                if last_request:
                    wait = random.uniform(args.delay_min, args.delay_max)
                    print(f'  Pausa: {wait:.1f}s', flush=True)
                    await asyncio.sleep(wait)
                attempts += 1
                temp.unlink(missing_ok=True)
                try:
                    last_request = True
                    message = await client.get_messages(entity, ids=job['id'])
                    if not message or not message.file:
                        raise RuntimeError('Mensagem ou mídia indisponível')
                    remote_name = getattr(message.file, 'name', '') or ''
                    if not remote_name.lower().endswith('.epub'):
                        raise RuntimeError('Mídia não é EPUB')
                    result = await asyncio.wait_for(
                        client.download_media(message, file=str(temp)),
                        timeout=args.download_timeout,
                    )
                    if not result or not temp.is_file():
                        raise RuntimeError('Download não concluído')
                    size = temp.stat().st_size
                    remote_size = getattr(message.file, 'size', None)
                    if not size or (remote_size is not None and size != remote_size):
                        raise RuntimeError('Tamanho inconsistente')
                    # Arquivo completo passa a ser visível somente após validação.
                    temp.replace(target)
                    event = {
                        'key': key, 'status': 'concluido', 'path': str(target),
                        'bytes': size, 'timestamp': datetime.now().isoformat(),
                    }
                    record_event(event)
                    completed[key] = event
                    ok += 1
                    break
                except FloodWaitError as exc:
                    wait = max(0, int(exc.seconds)) + 2
                    print(f'  FloodWait: Telegram exige {wait}s de espera.', flush=True)
                    if wait > args.max_flood_wait:
                        print('  Espera acima do limite configurado; interrompendo para retomar depois.')
                        return
                    await asyncio.sleep(wait)
                    # Não contabiliza como erro: tenta novamente a mesma mensagem.
                    last_request = False
                except (KeyboardInterrupt, asyncio.CancelledError):
                    raise
                except Exception as exc:
                    if attempts < args.retries:
                        print(f'  Tentativa {attempts} falhou: {exc}; tentando novamente.', flush=True)
                        continue
                    failed += 1
                    print(f'  ERRO após {attempts} tentativas: {exc}', flush=True)
                    record_event({
                        'key': key, 'status': 'erro', 'erro': str(exc),
                        'timestamp': datetime.now().isoformat(),
                    })
                    break
                finally:
                    temp.unlink(missing_ok=True)
        print(f'\nConcluídos: {ok} | Já existentes: {skipped} | Falhas: {failed}')
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--chat')
    parser.add_argument('--report-only', action='store_true', help='Gera apenas o TXT, sem conectar ao Telegram')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--api-id')
    parser.add_argument('--api-hash')
    parser.add_argument('--delay-min', type=float, default=8)
    parser.add_argument('--delay-max', type=float, default=15)
    parser.add_argument('--retries', type=int, default=3)
    parser.add_argument('--download-timeout', type=int, default=600,
                        help='Tempo maximo por tentativa de download em segundos (padrao: 600)')
    parser.add_argument('--max-flood-wait', type=int, default=3600,
                        help='Se Telegram exigir espera maior, parar e retomar depois (segundos)')
    args = parser.parse_args()
    if args.delay_min < 0 or args.delay_max < args.delay_min:
        parser.error('Intervalo de delay inválido')
    if args.download_timeout < 1:
        parser.error('--download-timeout deve ser maior que zero')
    if args.retries < 1 or args.max_flood_wait < 0:
        parser.error('--retries deve ser >= 1 e --max-flood-wait >= 0')
    if not CSV_PATH.exists():
        sys.exit(f'CSV não encontrado: {CSV_PATH}')
    jobs = build_jobs(read_csv(CSV_PATH))
    counts = Counter(j['status'] for j in jobs)
    print('Check Epub — Downloader')
    print('CSV:', CSV_PATH)
    print('Destino:', DEST)
    print('Para revisão:', counts['revisar'])
    print('Não encontrados:', counts['nao_encontrado'])
    print('Total selecionado:', len(jobs))
    print('Ordem: menor para maior tamanho (pendentes são retomados pelo manifesto)')
    if not args.chat:
        parser.error('Informe --chat para identificar as chaves do manifesto')
    pending, excluded, complete, conflicts = pending_jobs(jobs, args.chat)
    write_report(pending, excluded, complete, conflicts)
    print('Concluidos conferidos:', complete)
    print('Pendentes:', len(pending))
    print('Excluidos temporariamente (IDs 27799, 26276):', len(excluded))
    print('Existentes sem manifesto:', len(conflicts))
    print('Relatorio TXT:', REPORT)
    jobs = pending
    if args.limit is not None:
        if args.limit < 1:
            parser.error('--limit deve ser maior que zero')
        jobs = jobs[:args.limit]
        print('Limite desta execução:', len(jobs))
    print(f'Delay entre solicitações: {args.delay_min:g}–{args.delay_max:g}s')
    if args.dry_run or args.report_only:
        print('Simulação concluída. Nenhum download realizado.')
        return
    if not jobs:
        print('Nenhum download pendente.')
        return
    try:
        asyncio.run(download(args, jobs))
    finally:
        # Atualiza o relatorio com os arquivos que continuarem pendentes.
        pending, excluded, complete, conflicts = pending_jobs(build_jobs(read_csv(CSV_PATH)), args.chat)
        write_report(pending, excluded, complete, conflicts)
        print('Relatorio atualizado:', REPORT, '| Pendentes:', len(pending))


if __name__ == '__main__':
    main()

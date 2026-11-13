#!/usr/bin/env python3
"""Exporta metadados de mídias de um chat Telegram sem baixar anexos."""
import asyncio
import csv
import getpass
import os
from datetime import datetime, timezone
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename, MessageMediaPhoto, MessageMediaDocument

FIELDS = ['data_utc', 'id_mensagem', 'tipo', 'nome_arquivo', 'tamanho_bytes', 'link_mensagem']

async def main():
    print('=== Exportador de mídias do Telegram (somente metadados) ===')
    api_id = int(input('API ID: ').strip())
    api_hash = getpass.getpass('API hash (não aparece na tela): ').strip()
    session = str(Path.home() / '.telegram_extrator_midias')
    async with TelegramClient(session, api_id, api_hash) as client:
        dialogs = [d async for d in client.iter_dialogs() if d.is_group or d.is_channel]
        if not dialogs:
            print('Nenhum grupo ou canal acessível encontrado.')
            return
        for i, d in enumerate(dialogs, 1):
            print(f'{i:>3}. {d.name}')
        while True:
            try:
                idx = int(input('Número do grupo/canal: ')) - 1
                dialog = dialogs[idx]
                if idx < 0:
                    raise IndexError
                break
            except (ValueError, IndexError):
                print('Selecione um número válido.')
        year = input('Ano inicial [2024]: ').strip() or '2024'
        start = datetime(int(year), 1, 1, tzinfo=timezone.utc)
        output = Path.home() / 'Downloads' / f'telegram_midias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        count = 0
        scanned = 0
        with output.open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            async for msg in client.iter_messages(dialog.entity):
                if msg.date < start:
                    break
                scanned += 1
                media = msg.media
                if isinstance(media, MessageMediaPhoto):
                    kind, name, size = 'foto', '', ''
                elif isinstance(media, MessageMediaDocument):
                    doc = media.document
                    mime = getattr(doc, 'mime_type', '') or ''
                    kind = 'video' if mime.startswith('video/') else 'audio' if mime.startswith('audio/') else 'documento'
                    name = next((a.file_name for a in doc.attributes if isinstance(a, DocumentAttributeFilename)), '')
                    size = getattr(doc, 'size', '')
                else:
                    continue
                username = getattr(dialog.entity, 'username', None)
                link = f'https://t.me/{username}/{msg.id}' if username else ''
                writer.writerow({'data_utc': msg.date.isoformat(), 'id_mensagem': msg.id, 'tipo': kind,
                                 'nome_arquivo': name, 'tamanho_bytes': size, 'link_mensagem': link})
                count += 1
                if scanned % 1000 == 0:
                    print(f'{scanned} mensagens examinadas, {count} mídias encontradas...')
        print(f'Concluído: {count} mídias de {scanned} mensagens.\nCSV: {output}')
        print('Observação: fotos e algumas mídias não possuem nome original na API.')

if __name__ == '__main__':
    asyncio.run(main())

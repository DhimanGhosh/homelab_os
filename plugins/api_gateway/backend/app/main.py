from __future__ import annotations

import os
from pathlib import Path
import shutil
import requests
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

app = FastAPI(title='Homelab API Gateway', version='v1.3.0', description='API Gateway for Homelab services like Library, Dictionary, Statusboard, Navidrome, and more.')

class AddBookPayload(BaseModel):
    title: str
    author: str = ''
    isbn: str = ''
    notes: str = ''
LIB = os.getenv('LIBRARY_API', 'http://127.0.0.1:8132')
DICT = os.getenv('DICTIONARY_API', 'http://127.0.0.1:8133')
STATUSBOARD_API = os.getenv('STATUSBOARD_API', 'http://127.0.0.1:8131')
NAVIDROME_API = os.getenv('NAVIDROME_API', 'http://127.0.0.1:4533')
NEXTCLOUD_PATH = Path(os.getenv('NEXTCLOUD_STORAGE_PATH', '/opt/homelab/nextcloud/html'))
INCOMING_DROP_PATH = Path(os.getenv('INCOMING_DROP_PATH', '/opt/homelab/media_drop/Incoming'))


def ensure_incoming_dir():
    try:
        INCOMING_DROP_PATH.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Incoming drop path is not writable: {INCOMING_DROP_PATH} ({e})')


def proxy_json(url: str, method: str = 'GET', expected_json: bool = True, timeout: int = 20, **kwargs):
    try:
        r = requests.request(method, url, timeout=timeout, **kwargs)
        r.raise_for_status()
    except requests.RequestException as e:
        body = getattr(getattr(e, 'response', None), 'text', '')[:400]
        raise HTTPException(status_code=502, detail={'message': 'Upstream request failed', 'url': url, 'error': str(e), 'body': body})
    if not expected_json:
        return {'ok': True, 'status_code': r.status_code, 'text': r.text[:1000]}
    try:
        return r.json()
    except ValueError:
        raise HTTPException(status_code=502, detail={'message': 'Upstream did not return JSON', 'url': url, 'status_code': r.status_code, 'body': r.text[:400]})


@app.get('/api/health', tags=['gateway'])
def health():
    return {'ok': True, 'service': 'Homelab API Gateway'}


@app.get('/api/library/book-enquiry', tags=['library'])
def library_book_enquiry(author: str = '', title: str = '', q: str = ''):
    query = q or author or title
    return proxy_json(f'{LIB}/api/books/lookup', params={'author': author, 'title': title, 'q': query})


@app.get('/api/library/books', tags=['library'])
def library_books(q: str = '', genre: str = '', status: str = '', bookmarked: bool = False, sort_by: str = 'personalized_score', sort_dir: str = 'desc'):
    return proxy_json(f'{LIB}/api/books', params={'q': q, 'genre': genre, 'status': status, 'bookmarked': str(bookmarked).lower(), 'sort_by': sort_by, 'sort_dir': sort_dir}, timeout=30)


@app.get('/api/library/stats', tags=['library'])
def library_stats():
    return proxy_json(f'{LIB}/api/stats')




@app.get('/api/library/options', tags=['library'])
def library_options():
    return proxy_json(f'{LIB}/api/options')


@app.get('/api/library/settings', tags=['library'])
def library_settings():
    return proxy_json(f'{LIB}/api/settings')


@app.get('/api/library/books/{book_id}', tags=['library'])
def library_get_book(book_id: int):
    return proxy_json(f'{LIB}/api/books/{book_id}')


@app.patch('/api/library/books/{book_id}', tags=['library'])
def library_patch_book(book_id: int, payload: dict):
    return proxy_json(f'{LIB}/api/books/{book_id}', method='PATCH', json=payload, timeout=40)


@app.patch('/api/library/books/{book_id}/status', tags=['library'])
def library_patch_status(book_id: int, payload: dict):
    return proxy_json(f'{LIB}/api/books/{book_id}/status', method='PATCH', json=payload, timeout=20)


@app.delete('/api/library/books/{book_id}', tags=['library'])
def library_delete_book(book_id: int):
    return proxy_json(f'{LIB}/api/books/{book_id}', method='DELETE', timeout=20)


@app.get('/api/library/recommendation', tags=['library'])
def library_recommendation():
    return proxy_json(f'{LIB}/api/recommendation')


@app.post('/api/library/backup', tags=['library'])
def library_backup():
    return proxy_json(f'{LIB}/api/backup', method='POST', timeout=20)


@app.get('/api/library/backups', tags=['library'])
def library_backups():
    return proxy_json(f'{LIB}/api/backups', timeout=20)

@app.post('/api/library/add-book', tags=['library'])
def library_add_book(payload: AddBookPayload):
    required_title = payload.title.strip()
    if not required_title:
        raise HTTPException(status_code=400, detail='title is required')
    return proxy_json(f'{LIB}/api/books', method='POST', json={'title': required_title, 'author': payload.author.strip(), 'isbn': payload.isbn.strip(), 'notes': payload.notes.strip()}, timeout=40)


@app.post('/api/library/reverify/{book_id}', tags=['library'])
def library_reverify(book_id: int):
    return proxy_json(f'{LIB}/api/books/{book_id}/refresh', method='POST', timeout=40)


@app.post('/api/library/deduplicate', tags=['library'])
def library_deduplicate():
    return proxy_json(f'{LIB}/api/books/deduplicate', method='POST', timeout=40)


@app.get('/api/dictionary/lookup', tags=['dictionary'])
def dictionary_lookup(q: str = Query(..., min_length=1)):
    return proxy_json(f'{DICT}/api/lookup', params={'q': q})


@app.get('/api/statusboard/summary', tags=['statusboard'])
def statusboard_summary():
    return proxy_json(f'{STATUSBOARD_API}/api/summary')


@app.get('/api/navidrome/health', tags=['navidrome'])
def navidrome_health():
    try:
        r = requests.get(NAVIDROME_API, timeout=10)
        return {'ok': r.ok, 'status_code': r.status_code, 'base': NAVIDROME_API}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get('/api/media/incoming/list', tags=['media'])
def incoming_list():
    ensure_incoming_dir()
    items = []
    if INCOMING_DROP_PATH.exists():
        for p in sorted(INCOMING_DROP_PATH.iterdir()):
            if p.is_file():
                items.append({'name': p.name, 'size_bytes': p.stat().st_size})
    return {'path': str(INCOMING_DROP_PATH), 'count': len(items), 'items': items}


@app.post('/api/media/incoming/upload', tags=['media'])
def incoming_upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail='filename missing')
    ensure_incoming_dir()
    dest = INCOMING_DROP_PATH / Path(file.filename).name
    with dest.open('wb') as f:
        shutil.copyfileobj(file.file, f)
    return {'saved': True, 'path': str(dest), 'size_bytes': dest.stat().st_size}


@app.get('/api/nextcloud/storage', tags=['nextcloud'])
def nextcloud_storage():
    p = NEXTCLOUD_PATH
    if not p.exists():
        return {'path': str(p), 'exists': False}
    stat = os.statvfs(str(p))
    total = stat.f_frsize * stat.f_blocks
    free = stat.f_frsize * stat.f_bavail
    used = total - free
    return {'path': str(p), 'exists': True, 'total_bytes': total, 'used_bytes': used, 'free_bytes': free}


@app.get('/api/debug/upstreams', tags=['gateway'])
def debug_upstreams():
    out = {}
    for name, url in {
        'library': LIB + '/api/health',
        'dictionary': DICT + '/api/health',
        'statusboard': STATUSBOARD_API + '/api/summary',
        'navidrome': NAVIDROME_API,
    }.items():
        try:
            r = requests.get(url, timeout=8)
            out[name] = {'ok': r.ok, 'status_code': r.status_code, 'content_type': r.headers.get('content-type', ''), 'preview': r.text[:120]}
        except Exception as e:
            out[name] = {'ok': False, 'error': str(e)}
    out['incoming_drop_path'] = str(INCOMING_DROP_PATH)
    out['incoming_drop_exists'] = INCOMING_DROP_PATH.exists()
    out['incoming_drop_parent_exists'] = INCOMING_DROP_PATH.parent.exists()
    return out

@app.get('/api/apps', tags=['gateway'])
def installed_apps_summary():
    apps_base = Path('/mnt/nas/homelab/apps')
    items = []
    if apps_base.exists():
        for d in sorted(apps_base.iterdir()):
            payload = None
            for name in ('install_state.json', 'metadata.json'):
                p = d / name
                if p.exists():
                    try:
                        payload = json.loads(p.read_text())
                        break
                    except Exception:
                        payload = None
            if payload:
                items.append({
                    'id': payload.get('id', d.name),
                    'name': payload.get('name', d.name),
                    'version': payload.get('installed_version') or payload.get('version') or '-',
                    'port': payload.get('port', '-'),
                    'open_path': payload.get('open_path', '/'),
                })
    return {'count': len(items), 'items': items}

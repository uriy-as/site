#!/usr/bin/env python3
import hashlib
import os
import re
import sys
import json

import requests

BASE = 'https://www.pythonanywhere.com'
USER = os.environ.get('PA_USERNAME', '').strip()
PASSWORD = os.environ.get('PA_PASSWORD', '').strip()
DOMAIN = os.environ.get('PA_DOMAIN', '').strip() or f'{USER}.pythonanywhere.com'
SOURCE_FILE = os.environ.get('FLASK_FILE', '.github/scripts/flask_app.py')

if not USER or not PASSWORD:
    print('ERROR: PA_USERNAME and PA_PASSWORD env vars are required')
    sys.exit(1)

if not os.path.exists(SOURCE_FILE):
    print(f'ERROR: file not found: {SOURCE_FILE}')
    sys.exit(1)

with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
print(f'File: {SOURCE_FILE} ({len(content)} bytes, hash: {file_hash[:12]}...)')

s = requests.Session()
s.headers['User-Agent'] = 'deploy-flask (auto)'

def csrf_from(html):
    m = re.search(r'Anywhere\.csrfToken\s*=\s*["\']([^"\']+)["\']', html)
    return m.group(1) if m else None

def cookie_csrf():
    return s.cookies.get('csrftoken', '')

# Login
print('1. GET /login/')
r = s.get(f'{BASE}/login/', timeout=30)
r.raise_for_status()
csrf = csrf_from(r.text)
if not csrf:
    print('ERROR: could not find CSRF token on login page')
    sys.exit(1)

print('2. POST /login/')
r = s.post(f'{BASE}/login/', data={
    'csrfmiddlewaretoken': csrf,
    'auth-username': USER,
    'auth-password': PASSWORD,
    'login_view-current_step': 'auth',
}, headers={'Referer': f'{BASE}/login/'}, timeout=30)

if USER not in r.url:
    print(f'WARNING: login may have failed (redirected to {r.url})')
else:
    print(f'   Login OK')

# Get webapps page to find CSRF and check domain
print('3. GET webapps page')
r = s.get(f'{BASE}/user/{USER}/webapps/', timeout=30)
r.raise_for_status()
csrf2 = csrf_from(r.text) or cookie_csrf()
if not csrf2:
    print('ERROR: could not find CSRF token on webapps page')
    sys.exit(1)
print(f'   CSRF: {csrf2[:10]}...')

# Candidate file paths on the server, in priority order.
# PA serves the app from one of these; the previous version accepted the first
# HTTP 200 from the files API, which silently wrote the file to a path the web
# app does not load from. Now every upload is verified by reading it back.
candidates = [
    f'/home/{USER}/flask_app.py',
    f'/home/{USER}/{DOMAIN}/flask_app.py',
]

def api_path(remote_path):
    return f'{BASE}/api/v0/user/{USER}/files/path{remote_path}'

def upload(remote_path):
    return s.post(api_path(remote_path), files={'content': ('flask_app.py', content)},
                  headers={'Referer': f'{BASE}/user/{USER}/webapps/',
                           'X-CSRFToken': csrf2},
                  timeout=30)

def verify(remote_path):
    r = s.get(api_path(remote_path),
              headers={'Referer': f'{BASE}/user/{USER}/webapps/',
                       'X-CSRFToken': csrf2},
              timeout=30)
    if r.status_code != 200:
        return False, f'HTTP {r.status_code}'
    remote_hash = hashlib.sha256(r.content).hexdigest()
    if remote_hash == file_hash:
        return True, 'hash matches'
    return False, f'hash differs (remote {remote_hash[:12]}, local {file_hash[:12]})'

print('5. Upload via PA API v0 with read-back verification')
verified_path = None
for remote_path in candidates:
    try:
        r = upload(remote_path)
    except Exception as e:
        print(f'   {remote_path}: ERROR {e}')
        continue
    print(f'   {remote_path}: upload HTTP {r.status_code}')
    if r.status_code not in (200, 201):
        print(f'      {r.text[:160]}')
        continue
    ok, detail = verify(remote_path)
    print(f'      verify: {"OK - " if ok else "FAILED - "}{detail}')
    if ok:
        verified_path = remote_path
        break

if not verified_path:
    print('ERROR: file was not verified at any known path - web app still runs old code')
    sys.exit(1)

print(f'   VERIFIED at {verified_path}')

# Reload
print('6. Reload web app')
reload_url = f'{BASE}/user/{USER}/webapps/{DOMAIN}/reload'
r = s.post(reload_url, data={'csrfmiddlewaretoken': csrf2},
           headers={'Referer': f'{BASE}/user/{USER}/webapps/'}, timeout=30)
print(f'   Reload: {r.status_code}')
if r.status_code != 200:
    print('ERROR: reload failed')
    sys.exit(1)
print('DONE')

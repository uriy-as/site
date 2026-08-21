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

# Try file editor page to find the correct path
print('4. Try file editor URL patterns')
urls_to_try = [
    f'{BASE}/user/{USER}/webapps/{DOMAIN}/files/flask_app.py',
    f'{BASE}/user/{USER}/files/path/home/{USER}/{DOMAIN}/flask_app.py',
    f'{BASE}/user/{USER}/files/path/home/{USER}/flask_app.py',
    f'{BASE}/user/{USER}/webapps/{DOMAIN}/home/flask_app.py',
]

for url in urls_to_try:
    r = s.post(url, json={'action': 'check_hash', 'hash': file_hash},
               headers={'Referer': f'{BASE}/user/{USER}/webapps/',
                        'X-CSRFToken': csrf2,
                        'Content-Type': 'application/json'},
               timeout=15)
    status = r.status_code
    is_json = 'json' in r.headers.get('content-type', '')
    print(f'   {url.split(USER+\"/\")[1]}: {status} json={is_json}')
    if status == 200 and is_json:
        print(f'   FOUND! Using: {url}')
        break
    # Also try the upload directly
    if status != 404:
        print(f'   Response: {r.text[:200]}')

# Try API v0 approach (upload via multipart)
print('5. Try PA API v0 (files endpoint)')
api_urls = [
    f'{BASE}/api/v0/user/{USER}/files/path/home/{USER}/{DOMAIN}/flask_app.py',
    f'{BASE}/api/v0/user/{USER}/files/path/home/{USER}/flask_app.py',
]
for url in api_urls:
    try:
        r = s.post(url, files={'content': ('flask_app.py', content)},
                   headers={'Referer': f'{BASE}/user/{USER}/webapps/'},
                   timeout=30)
        print(f'   {url.split(USER+\"/\")[1]}: {r.status_code}')
        if r.status_code in (200, 201):
            print(f'   SUCCESS via API v0!')
            break
        print(f'   Response: {r.text[:200]}')
    except Exception as e:
        print(f'   Error: {e}')

# Reload
print('6. Reload web app')
reload_url = f'{BASE}/user/{USER}/webapps/{DOMAIN}/reload'
r = s.post(reload_url, data={'csrfmiddlewaretoken': csrf2},
           headers={'Referer': f'{BASE}/user/{USER}/webapps/'}, timeout=30)
print(f'   Reload: {r.status_code}')
print('DONE')

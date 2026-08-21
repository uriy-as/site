#!/usr/bin/env python3
import hashlib
import os
import re
import sys

import requests

BASE = 'https://www.pythonanywhere.com'
USER = os.environ.get('PA_USERNAME', '').strip()
PASSWORD = os.environ.get('PA_PASSWORD', '').strip()
DOMAIN = os.environ.get('PA_DOMAIN', '').strip() or f'{USER}.pythonanywhere.com'
FLASK_FILE = os.environ.get('FLASK_FILE', '.github/scripts/flask_app.py')

if not USER or not PASSWORD:
    print('ERROR: PA_USERNAME and PA_PASSWORD env vars are required')
    sys.exit(1)

if not os.path.exists(FLASK_FILE):
    print(f'ERROR: file not found: {FLASK_FILE}')
    sys.exit(1)

with open(FLASK_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
print(f'File: {FLASK_FILE} ({len(content)} bytes, hash: {file_hash[:12]}...)')

s = requests.Session()
s.headers['User-Agent'] = 'deploy-flask (auto)'

def csrf_from(html):
    m = re.search(r'Anywhere\.csrfToken\s*=\s*["\']([^"\']+)["\']', html)
    return m.group(1) if m else None

def cookie_csrf():
    return s.cookies.get('csrftoken', '')

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

if 'dashboard' not in r.url and 'username' not in r.url.lower() and USER not in r.url:
    print(f'WARNING: login may have failed (redirected to {r.url})')
else:
    print(f'   Login OK (redirected to {r.url})')

print('3. GET webapps page')
r = s.get(f'{BASE}/user/{USER}/webapps/', timeout=30)
r.raise_for_status()
csrf2 = csrf_from(r.text) or cookie_csrf()
if not csrf2:
    print('ERROR: could not find CSRF token on webapps page')
    sys.exit(1)

# Step 4: Check hash
print('4. Check hash')
file_url = f'{BASE}/user/{USER}/webapps/{DOMAIN}/home/{FLASK_FILE}'
r = s.post(file_url, json={'action': 'check_hash', 'hash': file_hash},
           headers={'Referer': f'{BASE}/user/{USER}/webapps/',
                    'X-CSRFToken': csrf2,
                    'Content-Type': 'application/json'},
           timeout=30)
print(f'   Hash check: {r.status_code} {r.text[:200]}')

if r.status_code == 200:
    try:
        data = r.json()
        if data.get('status') == 'ok':
            print('   Hash matches - no update needed')
            print('DONE (no changes)')
            sys.exit(0)
    except:
        pass

# Step 5: Upload file
print('5. Upload flask_app.py')
r = s.post(file_url, json={'new_contents': content},
           headers={'Referer': f'{BASE}/user/{USER}/webapps/',
                    'X-CSRFToken': csrf2,
                    'Content-Type': 'application/json'},
           timeout=60)
print(f'   Upload: {r.status_code} {r.text[:200]}')

if r.status_code not in (200, 302):
    print(f'ERROR: upload failed with status {r.status_code}')
    sys.exit(1)

# Step 6: Reload web app
print('6. Reload web app')
reload_url = f'{BASE}/user/{USER}/webapps/{DOMAIN}/reload'
r = s.post(reload_url, data={'csrfmiddlewaretoken': csrf2},
           headers={'Referer': f'{BASE}/user/{USER}/webapps/'}, timeout=30)
print(f'   Reload: {r.status_code}')

print('DONE - flask_app.py deployed and web app reloaded')

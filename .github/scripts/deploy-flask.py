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

# Discover which .py file the web app actually loads. Uploading to the wrong
# path is the failure mode that made an earlier run report success while the
# served code stayed unchanged.
discovered = []
for match in re.finditer(r'/home/[^"\'<>\s\\]+?\.py', r.text):
    path = match.group(0)
    if path not in discovered:
        discovered.append(path)
print(f'   Files referenced by the web app: {len(discovered)}')
for path in discovered[:15]:
    print(f'     {path}')

# Candidate file paths on the server: whatever the webapp config references
# first (that is the file the running app imports), then the usual locations.
candidates = discovered + [
    f'/home/{USER}/flask_app.py',
    f'/home/{USER}/{DOMAIN}/flask_app.py',
]
candidates = [p for p in candidates if p.endswith('flask_app.py')] or candidates
seen_paths = set()
candidates = [p for p in candidates if not (p in seen_paths or seen_paths.add(p))]
print(f'   Upload targets: {candidates}')

print('5. Upload via PA API v0 with read-back verification')
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

# Diagnostics: web app status + error log before reloading
print('5b. Web app diagnostics')
try:
    r = s.get(f'{BASE}/user/{USER}/webapps/{DOMAIN}/', timeout=30)
    print(f'   webapp page HTTP {r.status_code}')
    for pat in (r'Something went wrong', r'error', r'not running', r'currently running',
                r'was not started', r'reload'):
        m = re.search(pat, r.text, re.I)
        if m:
            a = max(0, m.start() - 120)
            snippet = re.sub(r'\s+', ' ', r.text[a:m.end() + 200])[:300]
            print(f'   [{pat}] {snippet}')
except Exception as e:
    print(f'   webapp page ERROR {e}')

for log_path in (f'/home/{USER}/logs/{DOMAIN}.error.log',
                 f'/home/{USER}/logs/{DOMAIN}.log',
                 f'/home/{USER}/mysite/logs/error.log'):
    try:
        r = s.get(api_path(log_path),
                  headers={'Referer': f'{BASE}/user/{USER}/webapps/',
                           'X-CSRFToken': csrf2}, timeout=30)
        if r.status_code == 200 and r.text.strip():
            print(f'   LOG {log_path}:')
            for line in r.text.splitlines()[-40:]:
                print('     | ' + line)
            break
        print(f'   LOG {log_path}: HTTP {r.status_code}')
    except Exception as e:
        print(f'   LOG {log_path}: ERROR {e}')

# Reload
print('6. Reload web app')
reload_url = f'{BASE}/user/{USER}/webapps/{DOMAIN}/reload'
ok = False
for attempt in range(3):
    try:
        r = s.post(reload_url, data={'csrfmiddlewaretoken': csrf2},
                   headers={'Referer': f'{BASE}/user/{USER}/webapps/'}, timeout=120)
        print(f'   Reload try {attempt + 1}: HTTP {r.status_code}')
        if r.status_code == 200:
            ok = True
            break
    except Exception as e:
        print(f'   Reload try {attempt + 1}: ERROR {type(e).__name__} {e}')
    import time as _t
    _t.sleep(20)

# Health check after reload
import time as _t
print('7. Health check')
healthy = False
for i in range(12):
    try:
        import requests as _rq
        hr = _rq.get(f'https://{DOMAIN}/', timeout=15)
        print(f'   attempt {i + 1}: HTTP {hr.status_code} {hr.text[:60]!r}')
        if hr.status_code == 200:
            healthy = True
            break
    except Exception as e:
        print(f'   attempt {i + 1}: {type(e).__name__}')
    _t.sleep(10)

if not ok or not healthy:
    print('ERROR: reload/health check failed')
    sys.exit(1)
print('DONE')

#!/usr/bin/env python3
import os
import re
import sys
import time

import requests

BASE = 'https://www.pythonanywhere.com'
USER = os.environ.get('PA_USERNAME', '').strip()
PASSWORD = os.environ.get('PA_PASSWORD', '').strip()
DOMAIN = os.environ.get('PA_DOMAIN', '').strip() or f'{USER}.pythonanywhere.com'

if not USER or not PASSWORD:
    print('ERROR: PA_USERNAME and PA_PASSWORD env vars are required')
    sys.exit(1)

s = requests.Session()
s.headers['User-Agent'] = 'pythonanywhere-renew (auto)'

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

print('3. GET /user/{user}/webapps/')
r = s.get(f'{BASE}/user/{USER}/webapps/', timeout=30)
r.raise_for_status()
csrf2 = csrf_from(r.text) or cookie_csrf()
if not csrf2:
    print('ERROR: could not find CSRF token on webapps page')
    sys.exit(1)

extend_url = f'{BASE}/user/{USER}/webapps/{DOMAIN}/extend'
print(f'4. POST {extend_url}')
r = s.post(extend_url, data={'csrfmiddlewaretoken': csrf2},
           headers={'Referer': f'{BASE}/user/{USER}/webapps/'}, timeout=30)

if r.status_code in (200, 302):
    print('SUCCESS: extension requested')
else:
    print(f'WARNING: extend returned status {r.status_code}')

time.sleep(2)
r = s.get(f'{BASE}/user/{USER}/webapps/', timeout=30)
expiry_matches = re.findall(r'expiry[^<]{0,60}|Expires[^<]{0,60}|(?:expires|expiry)[^0-9]{0,20}([\d-]+)', r.text, re.I)
print('Webapps page fetched to verify. Expiry hints:', expiry_matches[:3] if expiry_matches else 'none found')
print('DONE')

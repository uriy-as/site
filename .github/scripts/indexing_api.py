import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime
import jwt
import requests

SITEMAP_URL = 'https://uriy-as.org/sitemap.xml'
API_URL = 'https://indexing.googleapis.com/v3/urlNotifications:publish'
TOKEN_URL = 'https://oauth2.googleapis.com/token'

SCOPES = ['https://www.googleapis.com/auth/indexing']

def get_access_token(sa_info):
    now = int(time.time())
    payload = {
        'iss': sa_info['client_email'],
        'scope': SCOPES,
        'aud': TOKEN_URL,
        'iat': now,
        'exp': now + 3600,
    }
    signed_jwt = jwt.encode(payload, sa_info['private_key'], algorithm='RS256',
                            headers={'typ': 'JWT'})
    r = requests.post(TOKEN_URL, data={
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': signed_jwt,
    }, timeout=15)
    r.raise_for_status()
    return r.json()['access_token']

def get_sitemap_urls():
    r = requests.get(SITEMAP_URL, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = [loc.text for loc in root.findall('.//sm:loc', ns) if loc.text]
    return urls

def submit_url(token, url, action='URL_UPDATED'):
    r = requests.post(API_URL,
        json={'url': url, 'type': action},
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        timeout=15)
    return r.status_code, r.json()

def main():
    import sys
    if len(sys.argv) < 2:
        print('Usage: python indexing_api.py <path-to-service-account.json>')
        sys.exit(1)

    with open(sys.argv[1]) as f:
        sa_info = json.load(f)

    print(f'[{datetime.now():%H:%M:%S}] Getting access token...')
    token = get_access_token(sa_info)
    print(f'[{datetime.now():%H:%M:%S}] Token obtained')

    print(f'[{datetime.now():%H:%M:%S}] Fetching sitemap...')
    urls = get_sitemap_urls()
    print(f'[{datetime.now():%H:%M:%S}] Found {len(urls)} URLs')

    submitted = 0
    errors = 0
    for url in urls:
        try:
            status, body = submit_url(token, url)
            if status in (200, 201):
                submitted += 1
                print(f'  ✅ {url}')
            else:
                errors += 1
                print(f'  ❌ {url} — {status}: {body.get("error", {}).get("message", "")}')
        except Exception as e:
            errors += 1
            print(f'  ❌ {url} — {e}')
        time.sleep(0.5)

    print(f'\n[{datetime.now():%H:%M:%S}] Done: {submitted} submitted, {errors} errors')

if __name__ == '__main__':
    main()

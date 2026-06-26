import base64
import html
import json
import os
import re
from collections import Counter
from datetime import datetime, date

import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

@app.after_request
def cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = 'https://uriy-as.org'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    return resp

@app.route('/api/chat', methods=['OPTIONS'])
@app.route('/visit', methods=['OPTIONS'])
@app.route('/pixel', methods=['OPTIONS'])
def cors_preflight():
    return '', 200

STATS_FILE = '/home/Astap/mysite/visits.json'
LEADS_FILE = '/home/Astap/mysite/leads.json'

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
TELEGRAM_TOKEN = os.environ.get('TG_BOT_TOKEN') or ''
ADMIN_CHAT_ID = '1994948658'

SYSTEM_PROMPT = """�� - ����������� ��������� ������ WebStudio (uriy-as.org). ������� �� ������� �����. ������ ������ ���� ��������������, ��������� ���������� ����� � ������. ������� �� ������ "���������� � ���������" - �� ��� ������� �� ������� �������.
��������� ���������� ���� ��� �������:

������ � ���� (USD):

1. �������� ������:
   - ����-������� (1-3 ��������): �� $250, ���� 3-5 ����
   - ���� ��� ���� (���������������, ��������-�������): �� $600, ���� 7-14 ����

2. Telegram-����:
   - ���-������� (5 ������� ����, ����������): �� $130, ���� 2-3 ���
   - Telegram-��� �� GPT (AI-�����������, ���� �����, �����������): �� $400, ���� 5-10 ����

3. ������� ������ ��� Telegram:
   - �� 2000 ������: �� $50, ���� 1 ����
   - 2000-4000 ������: �� $80, ���� 1-2 ���
   - 4000-7000 ������: �� $130, ���� 1-2 ���
   - �� 7000 ������: �� $200, ���� 2 ���
   ����� 10 ������ - ������ 20%

4. SEO-�����������: �� $70/���

�����: ������ 30% ��� ������ 5 ��������!

��������: @uriy_as59 (Telegram ��� �����), uriy.as59@yandex.com, @NevWebStudio_bot
����� � �������: @webstudio_chanel (������ ��� ������, ��������)

������: USD, RUB, EUR, USDT, ������������.

������� �������:
- �� ������� � ����� ������� ���������� �����
- �� ������� � ������ ������� ���������� ���
- ���� ���������� "��� ��������" - �������� �������� � Telegram @uriy_as59
- ���� ������ �� �� ������� - ������ ��� ������� ���������
"""

def load_leads():
    try:
        with open(LEADS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_leads(leads):
    with open(LEADS_FILE, 'w') as f:
        json.dump(leads[-100:], f)

def load_visits():
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_visits(visits):
    with open(STATS_FILE, 'w') as f:
        json.dump(visits[-200:], f)

def detect_device(ua):
    ua_lower = (ua or '').lower()
    if not ua_lower:
        return 'unknown'
    if any(p in ua_lower for p in ['mobile', 'android', 'iphone', 'ipod', 'phone']):
        return 'mobile'
    if 'ipad' in ua_lower or ('tablet' in ua_lower):
        return 'tablet'
    if 'bot' in ua_lower or 'crawler' in ua_lower or 'spider' in ua_lower:
        return 'bot'
    return 'desktop'

PIXEL_GIF = base64.b64decode(
    'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
)

@app.route('/')
def index():
    return 'Visit tracker is running'

@app.route('/pixel')
def pixel():
    page = request.args.get('page', '/')
    ref = request.args.get('ref', '')
    screen = request.args.get('screen', '')
    ua = request.headers.get('User-Agent', '')
    visits = load_visits()
    visits.append({
        'page': page,
        'ref': ref,
        'screen': screen,
        'device': detect_device(ua),
        'ip': request.remote_addr or '',
        'ua': ua,
        'date': datetime.now().isoformat()
    })
    save_visits(visits)
    return Response(PIXEL_GIF, mimetype='image/gif')

@app.route('/visit', methods=['POST'])
def visit():
    data = request.json or {}
    ua = request.headers.get('User-Agent', '')
    visits = load_visits()
    visits.append({
        'page': data.get('page', '/'),
        'ref': data.get('ref', ''),
        'screen': data.get('screen', ''),
        'device': detect_device(ua),
        'ip': request.remote_addr or '',
        'ua': ua,
        'date': datetime.now().isoformat()
    })
    save_visits(visits)
    return jsonify({'ok': True})

@app.route('/api/lead', methods=['POST'])
def save_lead():
    data = request.json or {}
    message = data.get('message', '').strip() or data.get('msg', '').strip()
    if not message:
        return jsonify({'ok': False})
    leads = load_leads()
    leads.append({
        'name': data.get('name', ''),
        'email': data.get('email', ''),
        'phone': data.get('phone', ''),
        'message': message,
        'ip': request.remote_addr or '',
        'date': datetime.now().isoformat()
    })
    save_leads(leads)
    return jsonify({'ok': True, 'count': len(load_leads())})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    message = data.get('message', '')
    if not message:
        return jsonify({'reply': '�������� ��� ������.'})
    reply = ask_ai(message)
    return jsonify({'reply': reply})

def ask_gemini(text):
    payload = {
        'contents': [{
            'parts': [{'text': f'{SYSTEM_PROMPT}\n\n������ ������������: {text}'}]
        }],
        'generationConfig': {
            'maxOutputTokens': 600,
            'temperature': 0.8
        }
    }
    try:
        r = requests.post(
            'https://generativelanguage.googleapis.com/v1/models/gemini-3.1-flash-lite:generateContent?key=' + GEMINI_API_KEY,
            json=payload,
            timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            candidates = data.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                texts = [p['text'] for p in parts if 'text' in p]
                if texts:
                    return '\n'.join(texts)
    except:
        pass
    return None

def ask_hf(text):
    prompt = f"""{SYSTEM_PROMPT}

������ ������������: {text}

������ �� ������ ������������ ��������, ��������� ���������� ����."""
    headers = {}
    hf_token = os.environ.get('HF_API_TOKEN', '')
    if hf_token:
        headers['Authorization'] = f'Bearer {hf_token}'
    models = [
        'TinyLlama/TinyLlama-1.1B-Chat-v1.0',
        'google/flan-t5-large',
        'microsoft/DialoGPT-medium'
    ]
    for model in models:
        try:
            r = requests.post(
                f'https://api-inference.huggingface.co/models/{model}',
                json={'inputs': prompt, 'parameters': {'max_new_tokens': 400, 'temperature': 0.7}},
                headers=headers,
                timeout=60
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    gen = data[0].get('generated_text', '')
                elif isinstance(data, dict):
                    gen = data.get('generated_text', '')
                else:
                    gen = ''
                if gen:
                    for sep in ['������ �� ������', '�����:', '������ ������������:']:
                        idx = gen.find(sep)
                        if idx != -1:
                            after = gen[idx+len(sep):].strip()
                            parts = after.split('\n')
                            return '\n'.join(p for p in parts if p.strip())[:600]
                    return gen.strip()[:600]
            elif r.status_code == 503:
                model_loading = True
        except:
            continue
    return None

def ask_ai(text):
    reply = ask_hf(text)
    if reply:
        return reply
    reply = ask_gemini(text)
    if reply:
        return reply
    return ('��������, AI-��������� �������� ����������. '
            '�������� ��� � Telegram: @uriy_as59, � �� ������� �������.')

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    data = request.json
    if not data or 'message' not in data:
        return '', 200

    msg = data['message']
    chat_id = str(msg['chat']['id'])
    text = msg.get('text', '')

    if chat_id == ADMIN_CHAT_ID:
        if text == '/start':
            requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage', json={
                'chat_id': chat_id,
                'text': 'Bot works. New messages from clients will appear here.'
            })
        return '', 200

    if not text:
        return '', 200

    reply = ask_ai(text)

    requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage', json={
        'chat_id': int(chat_id),
        'text': reply,
        'parse_mode': 'HTML'
    })

    username = msg['chat'].get('username') or msg['chat'].get('first_name', 'Unknown')
    requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage', json={
        'chat_id': int(ADMIN_CHAT_ID),
        'text': f'<b>New question from bot</b>\n\nFrom: @{username}\n\n{text}',
        'parse_mode': 'HTML'
    })

    return '', 200

@app.route('/set_webhook')
def set_webhook():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Provide ?url= parameter'}), 400
    r = requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook', json={'url': url})
    return jsonify(r.json())

@app.route('/delete_webhook')
def delete_webhook():
    r = requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook')
    return jsonify(r.json())

@app.route('/stats')
@app.route('/stats.html')
def stats():
    visits = load_visits()
    total = len(visits)
    today_str = date.today().isoformat()
    today_count = sum(1 for v in visits if v['date'].startswith(today_str))
    unique_days = len(set(v['date'][:10] for v in visits))
    unique_ips = len(set(v['ip'] for v in visits))

    page_counts = Counter(v.get('page', '/') for v in visits)
    device_counts = Counter(v.get('device', 'unknown') for v in visits)

    rows = ''
    for v in reversed(visits[-50:]):
        d = v['date'][:19].replace('T', ' ')
        page = v.get('page', '/')
        dev = v.get('device', '')
        ip = v.get('ip', '')
        rows += f'''<tr>
            <td>{d}</td>
            <td>{page}</td>
            <td>{dev}</td>
            <td>{ip}</td>
        </tr>'''

    page_rows = ''
    for p, c in page_counts.most_common():
        page_rows += f'<tr><td>{p}</td><td>{c}</td></tr>'

    device_rows = ''
    for d, c in sorted(device_counts.items()):
        device_rows += f'<tr><td>{d}</td><td>{c}</td></tr>'

    lead_rows = ''
    for lead in reversed(load_leads()[-20:]):
        d = lead['date'][:19].replace('T', ' ')
        name = lead.get('name', '')
        phone = lead.get('phone', '')
        email = lead.get('email', '')
        msg = lead.get('message', '')
        ip = lead.get('ip', '')
        contact_info = ' | '.join(filter(None, [name, phone, email]))
        lead_rows += f'<tr><td>{d}</td><td>{html.escape(contact_info)}</td><td>{html.escape(msg)}</td><td>{ip}</td></tr>'

    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>���������� WebStudio</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:Arial,Helvetica,sans-serif; background:#f5f5f5; color:#222; padding:20px; line-height:1.5; }}
h1 {{ font-size:1.4rem; margin-bottom:16px; color:#333; }}
.stats {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }}
.card {{ background:#fff; padding:14px 20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1); flex:1; min-width:120px; text-align:center; }}
.card .num {{ font-size:1.6rem; font-weight:bold; color:#2563eb; }}
.card .label {{ font-size:0.8rem; color:#666; margin-top:2px; }}
h2 {{ font-size:1.1rem; margin:20px 0 10px; color:#444; }}
table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid #eee; font-size:0.88rem; }}
th {{ background:#f8f9fa; color:#555; font-weight:600; }}
tr:hover {{ background:#f0f7ff; }}
</style>
</head>
<body>
<h1>&#x1f4ca; ���������� WebStudio</h1>
<div class="stats">
    <div class="card"><div class="num">{total}</div><div class="label">����� �������</div></div>
    <div class="card"><div class="num">{today_count}</div><div class="label">�������</div></div>
    <div class="card"><div class="num">{unique_days}</div><div class="label">���� � �������</div></div>
    <div class="card"><div class="num">{unique_ips}</div><div class="label">���������� IP</div></div>
</div>

<h2>&#x1f4cc; ���������� �� ���������</h2>
<table><thead><tr><th>��������</th><th>�������</th></tr></thead><tbody>{page_rows}</tbody></table>

<h2>&#x1f4f1; �� �����������</h2>
<table><thead><tr><th>���</th><th>�������</th></tr></thead><tbody>{device_rows}</tbody></table>

<h2>&#x1f4e8; ������ � �����</h2>
<table><thead><tr><th>����</th><th>��������</th><th>���������</th><th>IP</th></tr></thead><tbody>{lead_rows}</tbody></table>

<h2>&#x1f4c4; ��������� 50 �������</h2>
<table><thead><tr><th>����</th><th>��������</th><th>����������</th><th>IP</th></tr></thead><tbody>{rows}</tbody></table>
</body>
</html>'''

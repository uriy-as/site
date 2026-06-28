import base64
import html
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, date, timedelta

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
_last_notify = 0.0

def send_tg(text):
    if not TELEGRAM_TOKEN:
        return
    try:
        requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True},
            timeout=10)
    except:
        pass

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.errorhandler(500)
def handle_500(e):
    send_tg(f'<b>❌ Что-то пошло не так</b>\nСтраница: {request.path}')
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def handle_404(e):
    send_tg(f'<b>⚠️ Страница не найдена</b>\n{request.path}')
    return jsonify({'error': 'Not found'}), 404

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
    dev = detect_device(ua)
    if dev not in ('bot', 'unknown'):
        visits = load_visits()
        visits.append({
            'page': page, 'ref': ref, 'screen': screen, 'device': dev,
            'ip': request.remote_addr or '', 'ua': ua,
            'date': datetime.now().isoformat()
        })
        save_visits(visits)
        if page != '/':
            global _last_notify
            now = time.time()
            if now - _last_notify > 60:
                _last_notify = now
                msg = f'<b>👤 Новый визит</b>\nСтраница: {page}\nУстройство: {dev}'
                if screen:
                    msg += f' ({screen})'
                if ref:
                    msg += f'\nReferrer: {ref}'
                msg += '\n<a href="https://astap.pythonanywhere.com/stats">📊 Статистика</a>'
                send_tg(msg)
    return Response(PIXEL_GIF, mimetype='image/gif')

@app.route('/visit', methods=['POST'])
def visit():
    data = request.json or {}
    ua = request.headers.get('User-Agent', '')
    dev = detect_device(ua)
    page = data.get('page', '/')
    if dev not in ('bot', 'unknown'):
        visits = load_visits()
        visits.append({
            'page': page, 'ref': data.get('ref', ''), 'screen': data.get('screen', ''), 'device': dev,
            'ip': request.remote_addr or '', 'ua': ua,
            'date': datetime.now().isoformat()
        })
        save_visits(visits)
        if page != '/':
            global _last_notify
            now = time.time()
            if now - _last_notify > 60:
                _last_notify = now
                ref = data.get('ref', '')
                screen = data.get('screen', '')
                msg = f'<b>👤 Новый визит</b>\nСтраница: {page}\nУстройство: {dev}'
                if screen:
                    msg += f' ({screen})'
                if ref:
                    msg += f'\nReferrer: {ref}'
                msg += '\n<a href="https://astap.pythonanywhere.com/stats">📊 Статистика</a>'
                send_tg(msg)
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
    parts = ['<b>📩 Новая заявка!</b>']
    name = data.get('name', '')
    phone = data.get('phone', '')
    email = data.get('email', '')
    if name:
        parts.append(f'Имя: {name}')
    if phone:
        parts.append(f'Телефон: {phone}')
    if email:
        parts.append(f'Email: {email}')
    parts.append(f'Сообщение: {message}')
    parts.append('<a href="https://astap.pythonanywhere.com/stats">📊 Статистика</a>')
    send_tg('\n'.join(parts))
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
    prompt = f"""{SYSTEM_PROMPT}\n\nВопрос клиента: {text}\n\nОтветь на вопрос клиента кратко, по-русски."""
    headers = {}
    hf_token = os.environ.get('HF_API_TOKEN', '')
    if hf_token:
        headers['Authorization'] = f'Bearer {hf_token}'
    models = [
        'Qwen/Qwen2.5-1.5B-Instruct',
        'Qwen/Qwen2.5-0.5B-Instruct',
        'google/flan-t5-large',
        'HuggingFaceH4/zephyr-7b-beta',
    ]
    for model in models:
        try:
            payload = {
                'inputs': prompt,
                'parameters': {'max_new_tokens': 500, 'temperature': 0.7, 'return_full_text': False},
            }
            r = requests.post(
                f'https://api-inference.huggingface.co/models/{model}',
                json=payload,
                headers=headers,
                timeout=90
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
                    return gen.strip()[:600]
            elif r.status_code == 503:
                continue
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
                'text': 'Бот работает. Новые сообщения от клиентов будут появляться здесь.'
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
        'text': f'<b>Новый вопрос от клиента</b>\n\nОт: @{username}\n\n{text}',
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

GA_PROPERTY_ID = '542628161'

GA_KEY_FILE = '/home/Astap/mysite/ga-key.json'

def get_ga4_metrics():
    key_json = os.environ.get('GA_SERVICE_KEY', '')
    if not key_json:
        try:
            with open(GA_KEY_FILE) as f:
                key_json = f.read()
        except (FileNotFoundError, IOError):
            pass
    if not key_json:
        return None, None, None, None
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            Dimension, Metric, RunRealtimeReportRequest
        )
        from google.oauth2.service_account import Credentials
        import json as j

        creds = Credentials.from_service_account_info(j.loads(key_json))
        client = BetaAnalyticsDataClient(credentials=creds)

        request = RunRealtimeReportRequest(
            property=f'properties/{GA_PROPERTY_ID}',
            metrics=[Metric(name='activeUsers'), Metric(name='screenPageViews')],
            dimensions=[Dimension(name='unifiedScreenName')]
        )
        response = client.run_realtime_report(request)

        total_users = 0
        total_views = 0
        pages = []
        for row in response.rows:
            path = row.dimension_values[0].value
            users = int(row.metric_values[0].value)
            views = int(row.metric_values[1].value)
            total_users += users
            total_views += views
            pages.append((path, views, users))

        pages.sort(key=lambda x: x[1], reverse=True)

        return (total_users, total_views, 0, pages[:10])
    except Exception as e:
        print(f'GA4 error: {e}')
        return None, None, None, None

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

    ga4_users, ga4_views, ga4_new, ga4_pages = get_ga4_metrics()
    ga4_block = ''
    if ga4_users is not None:
        ga4_page_rows = ''
        for path, views, users in ga4_pages:
            ga4_page_rows += f'<tr><td>{path}</td><td>{views}</td><td>{users}</td></tr>'
        ga4_block = f'''
<h2>&#x1f4e1; Google Analytics (за последние 30 минут)</h2>
<div class="stats">
    <div class="card"><div class="num">{ga4_users}</div><div class="label">Пользователи</div></div>
    <div class="card"><div class="num">{ga4_views}</div><div class="label">Просмотры</div></div>
    <div class="card"><div class="num">{ga4_new}</div><div class="label">Новые</div></div>
</div>
<table><thead><tr><th>Страница</th><th>Просмотры</th><th>Пользователи</th></tr></thead><tbody>{ga4_page_rows}</tbody></table>'''

    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Статистика WebStudio</title>
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
<h1>&#x1f4ca; Статистика WebStudio</h1>
<div class="stats">
    <div class="card"><div class="num">{total}</div><div class="label">Всего визитов</div></div>
    <div class="card"><div class="num">{today_count}</div><div class="label">Сегодня</div></div>
    <div class="card"><div class="num">{unique_days}</div><div class="label">Дней в записи</div></div>
    <div class="card"><div class="num">{unique_ips}</div><div class="label">Уникальных IP</div></div>
</div>
{ga4_block}
<h2>&#x1f4cc; Посещения по страницам</h2>
<table><thead><tr><th>Страница</th><th>Визитов</th></tr></thead><tbody>{page_rows}</tbody></table>

<h2>&#x1f4f1; По устройствам</h2>
<table><thead><tr><th>Тип</th><th>Визитов</th></tr></thead><tbody>{device_rows}</tbody></table>

<h2>&#x1f4e8; Заявки</h2>
<table><thead><tr><th>Дата</th><th>Контакты</th><th>Сообщение</th><th>IP</th></tr></thead><tbody>{lead_rows}</tbody></table>

<h2>&#x1f4c4; Последние 50 визитов</h2>
<table><thead><tr><th>Дата</th><th>Страница</th><th>Устройство</th><th>IP</th></tr></thead><tbody>{rows}</tbody></table>
</body>
</html>'''

send_tg(f'<b>🔄 Сервер запущен</b>\n{datetime.now().strftime("%d.%m.%Y %H:%M")}')




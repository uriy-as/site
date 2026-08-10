import base64
import html
import json
import os
import secrets
import shutil
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta

import requests
import re
from flask import Flask, request, jsonify, Response, abort

app = Flask(__name__)

ALLOWED_ORIGINS = {'https://uriy-as.org', 'https://www.uriy-as.org', 'https://astap.pythonanywhere.com'}

_rate = defaultdict(list)
_rate_lock = threading.Lock()

def check_origin():
    origin = request.headers.get('Origin', '')
    if not origin:
        return True
    return origin in ALLOWED_ORIGINS

def rate_limit(key, limit, window=60):
    now = time.time()
    with _rate_lock:
        ts = [t for t in _rate[key] if now - t < window]
        if len(ts) >= limit:
            _rate[key] = ts
            return False
        ts.append(now)
        _rate[key] = ts
    return True

def client_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''

@app.before_request
def protect():
    if request.method == 'OPTIONS':
        return None
    if not check_origin():
        return jsonify({'error': 'Forbidden'}), 403

@app.after_request
def cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = 'https://uriy-as.org'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return resp

@app.route('/api/chat', methods=['OPTIONS'])
@app.route('/api/stats', methods=['OPTIONS'])
@app.route('/visit', methods=['OPTIONS'])
@app.route('/pixel', methods=['OPTIONS'])
def cors_preflight():
    return '', 200

STATS_FILE = '/home/Astap/mysite/visits.json'
LEADS_FILE = '/home/Astap/mysite/leads.json'
BOT_HITS_FILE = '/home/Astap/mysite/bot_hits.json'

COHERE_API_KEY = os.environ.get('COHERE_API_KEY', '')
if not COHERE_API_KEY:
    try:
        with open('/home/Astap/mysite/cohere_key.txt') as f:
            COHERE_API_KEY = f.read().strip()
    except:
        pass
TELEGRAM_TOKEN = os.environ.get('TG_BOT_TOKEN') or ''
ADMIN_CHAT_ID = '1994948658'
PA_TOKEN_FILE = '/home/Astap/mysite/.pa_token'
def _load_pa_token():
    t = os.environ.get('PA_API_TOKEN', '')
    if t:
        return t
    try:
        with open(PA_TOKEN_FILE) as f:
            t = f.read().strip()
        if t:
            return t
    except FileNotFoundError:
        pass
    return ''
PA_API_TOKEN = _load_pa_token()
PA_USER = 'Astap'
PA_BASE = f'https://www.pythonanywhere.com/api/v0/user/{PA_USER}'
COHERE_MODEL = 'command-r-08-2024'
COHERE_BACKUP_MODEL = 'command-r'
_last_notify = 0.0

DIAG_KEY_FILE = '/home/Astap/mysite/.diag_key'
def _load_diag_key():
    k = os.environ.get('DIAG_KEY', '')
    if k:
        return k
    try:
        with open(DIAG_KEY_FILE) as f:
            k = f.read().strip()
        if k:
            return k
    except FileNotFoundError:
        pass
    k = secrets.token_urlsafe(16)
    try:
        with open(DIAG_KEY_FILE, 'w') as f:
            f.write(k)
    except Exception:
        pass
    return k

DIAG_KEY = _load_diag_key()

STATS_PASSWORD = ''
STATS_PASSWORD_FILE = '/home/Astap/mysite/.stats_password'
def _load_stats_password():
    p = os.environ.get('STATS_PASSWORD', '')
    if p:
        return p
    try:
        with open(STATS_PASSWORD_FILE) as f:
            p = f.read().strip()
        if p:
            return p
    except FileNotFoundError:
        pass
    return ''

STATS_PASSWORD = _load_stats_password()

def health_check():
    while True:
        time.sleep(3600)
        ok = False
        model = COHERE_MODEL
        try:
            r = requests.post('https://api.cohere.com/v1/chat',
                json={'message': 'Say hello in Russian', 'model': model},
                headers={'Authorization': f'Bearer {COHERE_API_KEY}'}, timeout=15)
            ok = r.status_code == 200
        except:
            pass
        if ok:
            continue

        send_tg('<b>⚠️ Cohere API error</b>\nПробую перезагрузку webapp...')
        try:
            requests.post(f'{PA_BASE}/webapps/astap.pythonanywhere.com/reload/',
                headers={'Authorization': f'Token {PA_API_TOKEN}'}, timeout=30)
            time.sleep(5)
            try:
                r = requests.post('https://api.cohere.com/v1/chat',
                    json={'message': 'Say hello in Russian', 'model': model},
                    headers={'Authorization': f'Bearer {COHERE_API_KEY}'}, timeout=15)
                ok = r.status_code == 200
            except:
                pass
        except:
            pass
        if ok:
            send_tg('<b>✅ Восстановлено</b>\nПерезагрузка webapp помогла.')
            continue

        send_tg('<b>⚠️ Cohere API error</b>\nПробую резервную модель command-r...')
        try:
            r = requests.post('https://api.cohere.com/v1/chat',
                json={'message': 'Say hello in Russian', 'model': COHERE_BACKUP_MODEL},
                headers={'Authorization': f'Bearer {COHERE_API_KEY}'}, timeout=15)
            ok = r.status_code == 200
            if ok:
                import sys
                this = sys.modules[__name__]
                this.COHERE_MODEL = COHERE_BACKUP_MODEL
                send_tg('<b>✅ Восстановлено</b>\nРезервная модель command-r активна.')
        except:
            pass
        if ok:
            continue

        send_tg('<b>🚨 Нужен человек</b>\nCohere API не работает. Ребут + смена модели не помогли.')

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

SYSTEM_PROMPT = """Ты — сотрудник веб-студии WebStudio (uriy-as.org). Общайся свободно и естественно, как живой человек. Отвечай на русском языке. Твоя задача — поддержать разговор, помочь с выбором услуги, подсказать по ценам.

КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО перечислять услуги в первом сообщении. Если клиент написал «привет», «здравствуйте», «добрый день» или аналогичное — твой первый ответ должен быть только приветствием и вопросом, чем помочь. Например: «Здравствуйте! Я консультант WebStudio. Чем могу помочь? Расскажите, что вас интересует.»

Перечисляй услуги списком только если клиент явно спросил «что вы предлагаете» или «какие у вас услуги». В остальных случаях сначала выясни потребность, задай уточняющие вопросы.

Для справки — услуги студии:

1. Сайт-визитка (1-3 стр): от $250, 3-5 дней
2. Сайт под ключ (лендинг, магазин, корпоративный): от $600, 7-14 дней
3. Бот-визитка (5 пунктов меню): от $130, 2-3 дня
4. Telegram-бот с AI (консультант, заявки, оплаты): от $400, 5-10 дней
5. Научные статьи: от $50 до $200 (зависит от объёма), пакет 10 статей — скидка 20%
6. SEO и раскрутка: от $70/мес

Акция: скидка 30% первым 5 клиентам.

Если спросят контакты — вот они: Telegram @uriy_as59, почта uriy.as59@yandex.com, раздел «Свяжитесь с нами» на сайте. Предлагай их только когда клиент хочет заказать или связаться, не надо в каждом ответе.

Не выдумывай услуги и цены — только то, что написано выше. Если не знаешь — так и скажи. Если хамят — не вступай в перепалку, вежливо закончи разговор.
"""

SYSTEM_PROMPT_EN = """You work at WebStudio (uriy-as.org). Chat naturally and freely — like a real person. Answer in English. Your job is to have a conversation, help choose a service, and share pricing info.

IMPORTANT: Don't list all services at once. First greet the client, ask what they need. Only list services if they explicitly ask "what do you offer" or "what services do you have".

Here's what the studio offers:

1. Business card website (1-3 pages): from $250, 3-5 days
2. Full website (landing, online store, corporate): from $600, 7-14 days
3. Business card bot (5 menu items): from $130, 2-3 days
4. Telegram bot with AI (consultant, orders, payments): from $400, 5-10 days
5. Science articles: from $50 to $200 (depends on length), 10-article pack — 20% off
6. SEO and promotion: from $70/month

Promo: 30% off for first 5 customers.

If someone asks for contacts: Telegram @uriy_as59, email uriy.as59@yandex.com, "Contact us" section on the website. Only share contacts when they want to order or get in touch — not after every message.

Don't make up services or prices — stick to what's above. If you don't know something, say so. If someone's rude — don't argue, just end the conversation politely.
"""

def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    shutil.move(tmp, path)

def load_leads():
    return load_json(LEADS_FILE)

def save_leads(leads):
    save_json(LEADS_FILE, leads[-100:])

def load_visits():
    return load_json(STATS_FILE)

def save_visits(visits):
    save_json(STATS_FILE, visits[-200:])

def load_bot_hits():
    return load_json(BOT_HITS_FILE)

def save_bot_hits(hits):
    save_json(BOT_HITS_FILE, hits[-500:])

def record_bot_hit(page, ua):
    ip = real_ip()
    if not rate_limit(f'bothit:{ip}', 20, 3600):
        return
    hits = load_bot_hits()
    hits.append({
        'page': page, 'ip': ip, 'ua': ua,
        'date': datetime.utcnow().isoformat()
    })
    save_bot_hits(hits)

INTERNAL_IPS = {'10.0.5.156', '10.0.0.0/8'}

def is_internal(ip):
    if ip.startswith('10.'):
        return True
    return False

def real_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''

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

_BOT_UA_MARKERS = [
    'headlesschrome', 'phantomjs', 'python-requests', 'python-urllib',
    'curl/', 'wget/', 'okhttp', 'apache-httpclient', 'go-http-client',
    'java/', 'node.js', 'axios', 'bot', 'crawler', 'spider', 'slurp',
    'bingpreview', 'majestic-', 'ahrefs', 'semrush', 'dotbot', 'petalbot',
    'yandexbot', 'googlebot', 'applebot', 'gptbot', 'bytespider',
    'facebookexternalhit', 'linkedinbot',
]
_ANDROID_K_RE = re.compile(r'linux; android [\d.]+; k\)')

def is_bot(ua):
    u = (ua or '').lower()
    if not u.strip():
        return True
    if _ANDROID_K_RE.search(u):
        return True
    return any(m in u for m in _BOT_UA_MARKERS)

PIXEL_GIF = base64.b64decode(
    'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
)

@app.route('/')
def index():
    return 'Visit tracker is running'

@app.route('/robots.txt')
def robots():
    r = ('User-agent: *\n'
         'Disallow: /stats\n'
         'Disallow: /stats.html\n'
         'Disallow: /api/\n'
         'Disallow: /visit\n'
         'Disallow: /pixel\n')
    return Response(r, mimetype='text/plain')

@app.route('/pixel')
def pixel():
    page = request.args.get('page', '/')
    ref = request.args.get('ref', '')
    screen = request.args.get('screen', '')
    ua = request.headers.get('User-Agent', '')
    dev = detect_device(ua)
    if screen and is_bot(ua):
        record_bot_hit(page, ua)
    if screen and not is_bot(ua) and not is_internal(real_ip()) and rate_limit(f'visit:{real_ip()}', 60, 3600):
        visits = load_visits()
        visits.append({
            'page': page, 'ref': ref, 'screen': screen, 'device': dev,
            'ip': real_ip(), 'ua': ua,
            'date': datetime.utcnow().isoformat()
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
                msg += f'\n<a href="https://astap.pythonanywhere.com/stats?key={DIAG_KEY}">📊 Статистика</a>'
                send_tg(msg)
    return Response(PIXEL_GIF, mimetype='image/gif')

@app.route('/visit', methods=['POST'])
def visit():
    data = request.json or {}
    ua = request.headers.get('User-Agent', '')
    dev = detect_device(ua)
    page = data.get('page', '/')
    if data.get('screen') and is_bot(ua):
        record_bot_hit(page, ua)
    if data.get('screen') and not is_bot(ua) and not is_internal(real_ip()) and rate_limit(f'visit:{real_ip()}', 60, 3600):
        visits = load_visits()
        visits.append({
            'page': page, 'ref': data.get('ref', ''), 'screen': data.get('screen', ''), 'device': dev,
            'ip': real_ip(), 'ua': ua,
            'date': datetime.utcnow().isoformat()
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
                msg += f'\n<a href="https://astap.pythonanywhere.com/stats?key={DIAG_KEY}">📊 Статистика</a>'
                send_tg(msg)
    return jsonify({'ok': True})

@app.route('/api/lead', methods=['POST'])
def save_lead():
    if not rate_limit(f'lead:{client_ip()}', 10, 300):
        return jsonify({'ok': False, 'error': 'Too many requests'}), 429
    data = request.json or {}
    if data.get('website') or data.get('company') or data.get('url'):
        return jsonify({'ok': True})
    message = data.get('message', '').strip() or data.get('msg', '').strip()
    if not message:
        return jsonify({'ok': False})
    if len(message) > 5000 or len(data.get('name', '')) > 200 or len(data.get('email', '')) > 200 or len(data.get('phone', '')) > 100:
        return jsonify({'ok': False}), 400
    leads = load_leads()
    leads.append({
        'name': data.get('name', ''),
        'email': data.get('email', ''),
        'phone': data.get('phone', ''),
        'message': message,
        'ip': real_ip(),
        'date': datetime.utcnow().isoformat()
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
    parts.append(f'<a href="https://astap.pythonanywhere.com/stats?key={DIAG_KEY}">📊 Статистика</a>')
    send_tg('\n'.join(parts))
    return jsonify({'ok': True, 'count': len(load_leads())})

@app.route('/api/stats')
def api_stats():
    if not rate_limit(f'stats-api:{real_ip()}', 30, 60):
        abort(429)
    key_ok = request.args.get('key') == DIAG_KEY
    origin = request.headers.get('Origin', '')
    site_ok = bool(origin) and origin in ALLOWED_ORIGINS
    if not key_ok and not site_ok:
        abort(403)
    from collections import Counter
    visits = load_visits()
    leads = load_leads()
    bot_hits = load_bot_hits()
    today_str = date.today().isoformat()
    real_visits = [v for v in visits if not is_internal(v.get('ip', ''))]
    today_real = sum(1 for v in real_visits if v['date'].startswith(today_str))
    page_counts = Counter(v.get('page', '/') for v in visits).most_common(10)
    device_counts = Counter(v.get('device', 'unknown') for v in visits)
    return jsonify({
        'today_real': today_real,
        'total_real': len(real_visits),
        'total_raw': len(visits),
        'today_raw': sum(1 for v in visits if v['date'].startswith(today_str)),
        'unique_ips': len(set(v['ip'] for v in visits)),
        'real_ips': len(set(v['ip'] for v in real_visits)),
        'days_recorded': len(set(v['date'][:10] for v in visits)),
        'leads_count': len(leads),
        'bot_hits': len(bot_hits),
        'bot_hits_today': sum(1 for b in bot_hits if b['date'].startswith(today_str)),
        'bot_ips': len(set(b['ip'] for b in bot_hits)),
        'pages': [{'path': p, 'count': c} for p, c in page_counts],
        'devices': [{'type': d, 'count': c} for d, c in device_counts.items()],
        'last_10': [{'date': v['date'][:19].replace('T', ' '), 'page': v.get('page', '/'), 'device': v.get('device', '')} for v in reversed(visits[-10:])],
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    if not rate_limit(f'chat:{client_ip()}', 20, 60):
        return jsonify({'error': 'Too many requests'}), 429
    data = request.json or {}
    message = data.get('message', '')
    lang = data.get('lang', 'ru')
    if not message:
        return jsonify({'reply': 'Пожалуйста, напишите сообщение.'})
    if len(message) > 4000:
        return jsonify({'reply': 'Сообщение слишком длинное.'})
    reply = ask_ai(message, lang)
    return jsonify({'reply': reply})

@app.route('/api/diag')
def diag():
    if request.args.get('key') != DIAG_KEY:
        abort(403)
    import traceback
    info = {'cohere_key_set': bool(COHERE_API_KEY), 'cohere_key_preview': COHERE_API_KEY[:8] + '...' if COHERE_API_KEY else ''}
    try:
        r = requests.post('https://api.cohere.com/v1/chat',
            json={'message': 'Say hello in Russian', 'model': COHERE_MODEL},
            headers={'Authorization': f'Bearer {COHERE_API_KEY}'}, timeout=10)
        info['cohere_status'] = r.status_code
        info['cohere_body'] = r.text[:500]
    except Exception as e:
        info['cohere_error'] = str(e)
        info['cohere_traceback'] = traceback.format_exc()
    return jsonify(info)



def ask_cohere(text):
    try:
        r = requests.post(
            'https://api.cohere.com/v1/chat',
            json={'message': f'{SYSTEM_PROMPT}\n\nВопрос клиента: {text}', 'model': COHERE_MODEL, 'temperature': 0.3},
            headers={'Authorization': f'Bearer {COHERE_API_KEY}'},
            timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('text'):
                return data['text']
    except:
        pass
    return None

def ask_cohere_en(text):
    try:
        r = requests.post(
            'https://api.cohere.com/v1/chat',
            json={'message': f'{SYSTEM_PROMPT_EN}\n\nClient question: {text}', 'model': COHERE_MODEL, 'temperature': 0.3},
            headers={'Authorization': f'Bearer {COHERE_API_KEY}'},
            timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('text'):
                return data['text']
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
                timeout=15
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

def ask_ai(text, lang='ru'):
    if lang == 'en':
        reply = ask_cohere_en(text)
        if reply:
            return reply
    else:
        reply = ask_cohere(text)
        if reply:
            return reply
    reply = ask_hf(text)
    if reply:
        return reply
    if lang == 'en':
        return ('Sorry, the AI assistant is temporarily unavailable. '
                'Contact us: Telegram @uriy_as59, email uriy.as59@yandex.com, '
                'or the contact form at https://uriy-as.org/index.html#contact')
    return ('Извините, AI-модели временно недоступны. '
            'Свяжитесь с нами: Telegram @uriy_as59, email uriy.as59@yandex.com, '
            'или через форму на сайте https://uriy-as.org/index.html#contact')

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
        'text': html.escape(reply),
        'parse_mode': 'HTML'
    })

    username = msg['chat'].get('username') or msg['chat'].get('first_name', 'Unknown')
    requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage', json={
        'chat_id': int(ADMIN_CHAT_ID),
        'text': f'<b>Новый вопрос от клиента</b>\n\nОт: @{html.escape(username)}\n\n{html.escape(text)}',
        'parse_mode': 'HTML'
    })

    return '', 200

@app.route('/set_webhook')
def set_webhook():
    if request.args.get('key') != DIAG_KEY:
        abort(403)
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Provide ?url= parameter'}), 400
    r = requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook', json={'url': url})
    return jsonify(r.json())

@app.route('/delete_webhook')
def delete_webhook():
    if request.args.get('key') != DIAG_KEY:
        abort(403)
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

        creds = Credentials.from_service_account_info(json.loads(key_json))
        client = BetaAnalyticsDataClient(credentials=creds)

        request = RunRealtimeReportRequest(
            property=f'properties/{GA_PROPERTY_ID}',
            metrics=[Metric(name='activeUsers'), Metric(name='screenPageViews'), Metric(name='newUsers')],
            dimensions=[Dimension(name='unifiedScreenName')]
        )
        response = client.run_realtime_report(request)

        total_users = 0
        total_views = 0
        total_new = 0
        pages = []
        for row in response.rows:
            path = row.dimension_values[0].value
            users = int(row.metric_values[0].value or 0)
            views = int(row.metric_values[1].value or 0)
            new_users = int(row.metric_values[2].value or 0)
            total_users += users
            total_views += views
            total_new += new_users
            pages.append((path, views, users))

        pages.sort(key=lambda x: x[1], reverse=True)

        return (total_users, total_views, total_new, pages[:10])
    except Exception as e:
        print(f'GA4 error: {e}')
        return None, None, None, None

_LOGIN_FAILS = defaultdict(list)
_LOGIN_FAILS_LOCK = threading.Lock()

def _login_locked(ip):
    with _LOGIN_FAILS_LOCK:
        fails = [t for t in _LOGIN_FAILS[ip] if time.time() - t < 600]
        _LOGIN_FAILS[ip] = fails
        return len(fails) >= 5

def _record_login_fail(ip):
    with _LOGIN_FAILS_LOCK:
        _LOGIN_FAILS[ip].append(time.time())

def _clear_login_fails(ip):
    with _LOGIN_FAILS_LOCK:
        _LOGIN_FAILS.pop(ip, None)

@app.route('/stats', methods=['GET', 'POST'])
@app.route('/stats.html', methods=['GET', 'POST'])
def stats():
    if not rate_limit(f'stats-page:{real_ip()}', 20, 60):
        return login_form('<b style="color:#d33">Слишком много запросов, попробуйте позже</b>')
    if request.method == 'POST':
        if _login_locked(real_ip()):
            return login_form('<b style="color:#d33">Временно заблокировано (попробуйте позже)</b>')
        if request.form.get('pass') == STATS_PASSWORD:
            _clear_login_fails(real_ip())
            return _render_stats()
        _record_login_fail(real_ip())
        if _login_locked(real_ip()):
            send_tg(f'<b>🚫 Блокировка входа в статистику</b>\nIP: {real_ip()}')
        return login_form('<b style="color:#d33">Неверный пароль</b>')
    if request.args.get('key') == DIAG_KEY or request.args.get('pass') == STATS_PASSWORD:
        return _render_stats()
    return login_form('')

def login_form(error=''):
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Вход в статистику</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:Arial,Helvetica,sans-serif; background:#f5f5f5; color:#222; padding:20px; display:flex; align-items:center; justify-content:center; min-height:100vh; }}
.login {{ background:#fff; padding:32px; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,0.12); width:100%; max-width:340px; text-align:center; }}
.login h1 {{ font-size:1.2rem; margin-bottom:16px; color:#333; }}
.login input {{ width:100%; padding:12px; font-size:1.1rem; border:1px solid #ccc; border-radius:6px; margin-bottom:12px; text-align:center; letter-spacing:0.15em; }}
.login button {{ width:100%; padding:12px; background:#2563eb; color:#fff; border:none; border-radius:6px; font-size:1rem; cursor:pointer; }}
.login button:hover {{ background:#1d4ed8; }}
.login .err {{ margin-bottom:12px; }}
.login .note {{ margin-top:14px; font-size:0.8rem; color:#888; }}
</style>
</head>
<body>
<form class="login" method="post">
<h1>&#x1f512; Вход в статистику</h1>
<div class="err">{error}</div>
<input type="password" name="pass" placeholder="Пароль" autofocus required>
<button type="submit">Войти</button>
<p class="note">Доступ только для владельца сайта</p>
</form>
</body>
</html>'''

def _render_stats():
    visits = load_visits()
    real_visits = [v for v in visits if not is_internal(v.get('ip', ''))]
    total = len(visits)
    real_total = len(real_visits)
    today_str = date.today().isoformat()
    today_count = sum(1 for v in visits if v['date'].startswith(today_str))
    today_real = sum(1 for v in real_visits if v['date'].startswith(today_str))
    unique_days = len(set(v['date'][:10] for v in visits))
    unique_ips = len(set(v['ip'] for v in visits))
    real_ips = len(set(v['ip'] for v in real_visits))
    bot_hits = load_bot_hits()
    today_str_bot = date.today().isoformat()
    bot_today = sum(1 for b in bot_hits if b['date'].startswith(today_str_bot))
    bot_ips = len(set(b['ip'] for b in bot_hits))

    page_counts = Counter(v.get('page', '/') for v in visits)

    rows = ''
    for v in reversed(visits[-50:]):
        d = v['date'][:19].replace('T', ' ')
        page = html.escape(v.get('page', '/'))
        dev = html.escape(v.get('device', ''))
        ip = html.escape(v.get('ip', ''))
        internal_tag = ' 🔒' if is_internal(v.get('ip', '')) else ''
        rows += f'''<tr>
            <td>{d}</td>
            <td>{page}</td>
            <td>{dev}</td>
            <td>{ip}{internal_tag}</td>
        </tr>'''

    page_rows = ''
    for p, c in page_counts.most_common():
        page_rows += f'<tr><td>{html.escape(p)}</td><td>{c}</td></tr>'

    device_rows = ''
    for d, c in sorted(Counter(v.get('device', 'unknown') for v in visits).items()):
        device_rows += f'<tr><td>{html.escape(d)}</td><td>{c}</td></tr>'

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

    bot_rows = ''
    for b in reversed(bot_hits[-50:]):
        d = b['date'][:19].replace('T', ' ')
        bpage = html.escape(b.get('page', '/'))
        bip = html.escape(b.get('ip', ''))
        bua = html.escape((b.get('ua', '') or '')[:80])
        bot_rows += f'<tr><td>{d}</td><td>{bpage}</td><td>{bip}</td><td>{bua}</td></tr>'

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
.card.green .num {{ color:#16a34a; }}
.card.orange .num {{ color:#ea580c; }}
.card.red .num {{ color:#d33; }}
h2 {{ font-size:1.1rem; margin:20px 0 10px; color:#444; }}
table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid #eee; font-size:0.88rem; }}
th {{ background:#f8f9fa; color:#555; font-weight:600; }}
tr:hover {{ background:#f0f7ff; }}
a {{ color:#2563eb; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
</style>
</head>
<body>
<h1>&#x1f4ca; Статистика WebStudio</h1>
<div class="stats">
    <div class="card green"><div class="num">{today_real}</div><div class="label">Реальных сегодня</div></div>
    <div class="card"><div class="num">{real_total}</div><div class="label">Реальных всего</div></div>
    <div class="card"><div class="num">{real_ips}</div><div class="label">Уникальных IP</div></div>
    <div class="card"><div class="num">{unique_days}</div><div class="label">Дней в записи</div></div>
</div>
<div class="stats">
    <div class="card orange"><div class="num">{total}</div><div class="label">Всего визитов (с тех.)</div></div>
    <div class="card"><div class="num">{today_count}</div><div class="label">Сегодня всего</div></div>
    <div class="card red"><div class="num">{len(bot_hits)}</div><div class="label">Ботов всего</div></div>
    <div class="card red"><div class="num">{bot_today}</div><div class="label">Ботов сегодня</div></div>
    <div class="card red"><div class="num">{bot_ips}</div><div class="label">IP ботов</div></div>
    <div class="card"><div class="num">
        <a href="https://metrica.yandex.com/dashboard?id=109350815" target="_blank">&#x2197;</a>
    </div><div class="label">Яндекс.Метрика</div></div>
</div>
{ga4_block}
<h2>&#x1f4cc; Посещения по страницам</h2>
<table><thead><tr><th>Страница</th><th>Визитов</th></tr></thead><tbody>{page_rows}</tbody></table>

<h2>&#x1f4f1; По устройствам</h2>
<table><thead><tr><th>Тип</th><th>Визитов</th></tr></thead><tbody>{device_rows}</tbody></table>

<h2>&#x1f4e8; Заявки</h2>
<table><thead><tr><th>Дата</th><th>Контакты</th><th>Сообщение</th><th>IP</th></tr></thead><tbody>{lead_rows}</tbody></table>

<h2>&#x1f41e; Последние заблокированные боты</h2>
<table><thead><tr><th>Дата</th><th>Страница</th><th>IP</th><th>User-Agent</th></tr></thead><tbody>{bot_rows}</tbody></table>

<h2>&#x1f4c4; Последние 50 визитов</h2>
<table><thead><tr><th>Дата</th><th>Страница</th><th>Устройство</th><th>IP</th></tr></thead><tbody>{rows}</tbody></table>
<p style="color:#888;font-size:0.8rem;margin-top:8px">🔒 — внутренний IP (мониторинг), не учитывается в &laquo;Реальных&raquo;</p>
</body>
</html>'''

send_tg(f'<b>🔄 Сервер запущен</b>\n{datetime.utcnow().strftime("%d.%m.%Y %H:%M")}')
threading.Thread(target=health_check, daemon=True).start()




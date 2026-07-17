import json, os, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

GH_PAT = os.environ['GH_PAT']
TOKEN = os.environ['TELEGRAM_TOKEN']
ADMIN = os.environ['ADMIN_CHAT_ID']

repo = 'uriy-as/uriy-as.github.io'
headers = {
    'Authorization': f'token {GH_PAT}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'daily-stats/1.0'
}

def gh_api(path):
    req = urllib.request.Request(f'https://api.github.com/repos/{repo}/{path}', headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def tg_send(text):
    data = json.dumps({'chat_id': ADMIN, 'text': text, 'parse_mode': 'HTML'}).encode()
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{TOKEN}/sendMessage',
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)

# GitHub Traffic API
try:
    traffic = gh_api('traffic/views')
except Exception as e:
    tg_send(f'\u274c Ошибка статистики: не удалось получить данные\n{str(e)}')
    exit(1)

yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
y_views = sum(d['count'] for d in traffic.get('views', []) if d['timestamp'].startswith(yesterday))
y_unique = sum(d['uniques'] for d in traffic.get('views', []) if d['timestamp'].startswith(yesterday))

total_views = traffic.get('count', 0)
total_unique = traffic.get('uniques', 0)

# Try to get referring sites (top 10)
refs = gh_api('traffic/popular/referrers')[:5]
ref_lines = ''
if refs:
    for r in refs:
        ref_lines += f'\n  \u2022 {r["referrer"]} \u2014 {r["count"]}'

# Try to get popular content (top 5)
content = gh_api('traffic/popular/paths')[:5]
content_lines = ''
if content:
    for c in content:
        content_lines += f'\n  \u2022 {c["path"]} \u2014 {c["count"]} просмотров, {c["uniques"]} уникальных'

# Clones data
try:
    clones = gh_api('traffic/clones')
    total_clones = clones.get('count', 0)
    total_clone_unique = clones.get('uniques', 0)
    y_clones = sum(d['count'] for d in clones.get('clones', []) if d['timestamp'].startswith(yesterday))
    y_clone_unique = sum(d['uniques'] for d in clones.get('clones', []) if d['timestamp'].startswith(yesterday))
except:
    total_clones = total_clone_unique = y_clones = y_clone_unique = 0

lines = []
lines.append(f'\U0001f4ca Статистика за {yesterday}')
lines.append('')
lines.append(f'\U0001f441 Просмотров вчера: {y_views} (уникальных: {y_unique})')
lines.append(f'\U0001f4c8 Всего за 14 дней: {total_views} (уникальных: {total_unique})')
if total_clones:
    lines.append(f'\U0001f4be Клонов вчера: {y_clones} (уникальных: {y_clone_unique})')
    lines.append(f'\U0001f4e6 Клонов за 14 дней: {total_clones} (уникальных: {total_clone_unique})')
lines.append('')
lines.append(f'\U0001f310 Откуда приходят:{ref_lines}')
lines.append('')
lines.append(f'\U0001f4cc Популярные страницы:{content_lines}')

tg_send('\n'.join(lines))

# Generate stats.html
def esc(s):
    import html
    return html.escape(str(s))

def fmt_count(val):
    return str(val) if val else '0'

html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Статистика WebStudio</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:Arial,Helvetica,sans-serif; background:#f5f5f5; color:#222; padding:20px; line-height:1.5; }}
h1 {{ font-size:1.4rem; margin-bottom:4px; color:#333; }}
.meta {{ font-size:0.85rem; color:#888; margin-bottom:20px; }}
.grid {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }}
.card {{ background:#fff; padding:14px 20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1); flex:1; min-width:120px; text-align:center; }}
.card .num {{ font-size:1.6rem; font-weight:bold; color:#2563eb; }}
.card .label {{ font-size:0.8rem; color:#666; margin-top:2px; }}
h2 {{ font-size:1.1rem; margin:20px 0 10px; color:#444; }}
table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid #eee; font-size:0.88rem; }}
th {{ background:#f8f9fa; color:#555; font-weight:600; }}
tr:hover {{ background:#f0f7ff; }}
a {{ color:#2563eb; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.note {{ color:#888; font-size:0.8rem; margin-top:8px; }}
</style>
</head>
<body>
<h1>&#x1f4ca; Статистика WebStudio</h1>
<p class="meta">Данные за последние 14 дней (GitHub Traffic API) &middot; Обновлено: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC</p>

<div class="grid">
    <div class="card"><div class="num">{fmt_count(total_views)}</div><div class="label">Просмотров за 14 дней</div></div>
    <div class="card"><div class="num">{fmt_count(total_unique)}</div><div class="label">Уникальных посетителей</div></div>
</div>
<div class="grid">
    <div class="card"><div class="num">{fmt_count(y_views)}</div><div class="label">Просмотров вчера</div></div>
    <div class="card"><div class="num">{fmt_count(y_unique)}</div><div class="label">Уникальных вчера</div></div>
</div>'''

if total_clones:
    html += f'''
<div class="grid">
    <div class="card"><div class="num">{fmt_count(total_clones)}</div><div class="label">Клонов за 14 дней</div></div>
    <div class="card"><div class="num">{fmt_count(total_clone_unique)}</div><div class="label">Уникальных клонов</div></div>
    <div class="card"><div class="num">{fmt_count(y_clones)}</div><div class="label">Клонов вчера</div></div>
    <div class="card"><div class="num">{fmt_count(y_clone_unique)}</div><div class="label">Уникальных клонов вчера</div></div>
</div>'''

if refs:
    html += '<h2>&#x1f310; Откуда приходят</h2><table><thead><tr><th>Источник</th><th>Переходов</th></tr></thead><tbody>'
    for r in refs:
        html += f'<tr><td>{esc(r["referrer"])}</td><td>{r["count"]}</td></tr>'
    html += '</tbody></table>'

if content:
    html += '<h2>&#x1f4cc; Популярные страницы</h2><table><thead><tr><th>Страница</th><th>Просмотров</th><th>Уникальных</th></tr></thead><tbody>'
    for c in content:
        html += f'<tr><td>{esc(c["path"])}</td><td>{c["count"]}</td><td>{c["uniques"]}</td></tr>'
    html += '</tbody></table>'

html += '''
<p class="note">&#x1f517; Подробная статистика в реальном времени: <a href="https://astap.pythonanywhere.com/stats" target="_blank">astap.pythonanywhere.com/stats</a></p>
</body>
</html>'''

output_path = os.path.join(os.environ.get('GITHUB_WORKSPACE', '.'), 'stats.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'stats.html written to {output_path}')

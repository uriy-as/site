import os
import json
import random
import urllib.request
import urllib.error

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID', '@webstudio_chanel')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

TOPICS = [
    "создание сайтов под ключ",
    "разработка Telegram-ботов с ИИ",
    "SEO-оптимизация сайтов в 2026",
    "как ИИ меняет веб-разработку",
    "лендинг или многостраничный сайт",
    "чат-боты для бизнеса",
    "скорость загрузки и конверсия",
    "безопасность сайта для малого бизнеса",
    "тренды веб-дизайна 2026",
    "автоматизация бизнеса с Telegram-ботами",
    "Mobile First: почему это важно",
    "нейросети для контента",
    "бесплатные инструменты для продвижения",
    "как выбрать хостинг для сайта",
    "типичные ошибки в лендингах",
    "зачем сайту блог",
    "аналитика для сайта: что отслеживать",
    "как написать ТЗ на сайт",
    "продвижение Telegram-канала",
    "автоматизация рассылок с ботами"
]

SYSTEM_PROMPT = """Ты — SMM-менеджер веб-студии WebStudio.

Чем занимаемся:
— Создание сайтов под ключ (лендинги, многостраничные, интернет-магазины)
— Разработка Telegram-ботов с искусственным интеллектом
— SEO-оптимизация и поддержка сайтов

Напиши пост для Telegram-канала @webstudio_chanel.

Требования к посту:
- Язык: русский
- Длина: 200-400 символов
- Стиль: полезный, экспертный, без воды
- Emoji: 2-4 уместных эмодзи
- В конце контакты:
🌐 Заказать: https://uriy-as.org
✉️ uriy.as59@yandex.com
- Без хештегов
- Пиши как живой эксперт, а не реклама"""


def generate_post():
    topic = random.choice(TOPICS)

    body = json.dumps({
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nТема поста: \"{topic}\""}]
        }]
    }).encode()

    req = urllib.request.Request(
        f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}',
        data=body,
        headers={'Content-Type': 'application/json'}
    )

    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"Gemini API error {e.code}: {err}")
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise


def send_post(text):
    data = json.dumps({
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }).encode()

    req = urllib.request.Request(
        f'https://api.telegram.org/bot{TOKEN}/sendMessage',
        data=data,
        headers={'Content-Type': 'application/json'}
    )

    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        if result.get('ok'):
            print(f"OK: Post sent to {CHAT_ID}")
        else:
            print(f"FAIL: {result}")
            exit(1)
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR: {e.code} {e.read().decode()}")
        exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)


if __name__ == '__main__':
    if not TOKEN:
        print("ERROR: TELEGRAM_TOKEN not set")
        exit(1)
    if not GEMINI_KEY:
        print("ERROR: GEMINI_API_KEY not set")
        exit(1)

    post = generate_post()
    print(f"Generated:\n{post}\n")
    send_post(post)

import os
import json
from openai import OpenAI

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID', '@webstudio_chanel')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY')

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
    "как выбрать хостинг для сайта"
]

client = OpenAI(api_key=OPENAI_KEY)

def generate_post():
    import random
    topic = random.choice(TOPICS)

    prompt = f"""Ты — SMM-менеджер веб-студии. Напиши пост для Telegram-канала @webstudio_chanel на тему: "{topic}".

Требования:
- Язык: русский
- Длина: 200-400 символов
- Стиль: полезный, экспертный, без воды
- Emoji: 2-4 уместных эмодзи
- В конце обязательно укажи контакты:
🌐 Заказать: https://uriy-as.org
✉️ uriy.as59@yandex.com

Не используй хештеги. Пиши как живой эксперт, а не рекламный бот."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=600
    )

    return response.choices[0].message.content.strip()


def send_post(text):
    import urllib.request
    import urllib.error

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
    if not OPENAI_KEY:
        print("ERROR: OPENAI_API_KEY not set")
        exit(1)

    post = generate_post()
    print(f"Generated:\n{post}\n")
    send_post(post)

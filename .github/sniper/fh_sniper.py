import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
SEEN = LOG = BIDS = ""
RSS = "https://freelancehunt.com/ua/projects.rss"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

TG_TOKEN = os.environ.get("SNIPER_TG_TOKEN", "")
TG_CHAT = os.environ.get("SNIPER_TG_CHAT", "1994948658")


def set_state_dir(d):
    global SEEN, LOG, BIDS
    os.makedirs(d, exist_ok=True)
    SEEN = os.path.join(d, "fh_sniper_seen.json")
    LOG = os.path.join(d, "fh_sniper_matches.log")
    BIDS = os.path.join(d, "fh_sniper_bids.json")


set_state_dir(BASE)
PORTFOLIO = "https://uriy-as.org"

WHITELIST_CAT = {
    "HTML та CSS верстання", "Веб-програмування", "PHP", "Супровід сайтів",
    "Налаштування ПЗ та серверів", "SEO-аудит сайтів", "Пошукова оптимізація (SEO)",
    "Створення сайту під ключ", "Інтеграція платіжних систем", "Тестування та QA",
    "Збір інформації", "Контент-менеджер", "Інтернет-магазини та електронна комерція",
}
TITLE_KW = re.compile(
    r"сайт|верстк|wordpress|вордпрес|лендінг|лендинг|\bhtml\b|\bcss\b|javascript"
    r"|\bphp\b|frontend|backend|телеграм|\bбот\b|\bбота\b|\bботи\b|\bботів\b|\bbot\b"
    r"|парсинг|парсер|scrap|\bseo\b|\bсео\b|скрипт|автоматизац|\bcrm\b|\bapi\b"
    r"|opencart|shopify|tilda|хостинг|домен|magento|інтеграц", re.I)

TEMPL = [
    # (ключи, текст-строка, цена, дни, вопрос)  — порядок = приоритет
    (("qa", "тестуван", "баг-репорт", "баг репорт"),
     "Проведу аудит за вашим ТЗ: матриця відповідності функціоналу, детальний баг-репорт (кроки відтворення, скрін/відео, пріоритети), ретест після правок розробника та коротке навчання власника по ключових діях.",
     2000, "3", "чи є ТЗ і тестові доступи до сайту та адмінки?"),
    (("wordpress", "вордпрес", "php", "opencart", "magento", "cms", "плагін", "міграці", "перенос", "перенес", "домен", "хостинг"),
     "Виконаю роботи під WordPress/PHP/CMS: міграцію та перенос (з бекапами, 301-редиректами і збереженням SEO), оновлення ядра й плагінів, правки шаблону, поля ACF, прискорення, конвертацію зображень у WebP. Працюю акуратно, з резервними копіями.",
     4000, "4", "яка CMS/версія і чи є доступи до хостингу та адмінки?"),
    (("парсинг", "парсер", "scrap", "збір інформації", "база даних", "вибірка"),
     "Зроблю парсер під ваші джерела: збір, чистка й структурування даних (таблиця / CSV / Google Sheets), з дедуплікацією та перевіркою. За потреби — оновлення за розкладом.",
     2000, "3", "з яких джерел збирати і в якому форматі потрібен результат (таблиця/CSV)?"),
    (("telegram", "телеграм", "бот", "bot"),
     "Розроблю Telegram-бота під ваш сценарій: прийом заявок/розсилки, меню, адмін-панель, інтеграції (оплата, CRM, Google) та хостинг. Після запуску — інструкція й підтримка.",
     3000, "4", "які функції потрібні (розсилка, оплата, адмінка) і чи є готовий сценарій?"),
    (("seo", "сео", "пошукова", "семантик", "просуванн"),
     "Зроблю SEO-аудит: технічна перевірка (індексація, швидкість, дублі, мікророзмітка), аналіз структури й мета-тегів, збір семантики, план пріоритетних правок і рекомендації по контенту.",
     2500, "4", "які цільові запити та регіон просування?"),
    (("верстк", "лендінг", "лендинг", "html", "css", "frontend", "адаптив"),
     "Зверстаю pixel-perfect 1:1 за макетом: повний адаптив (десктоп/планшет/мобільний), базове SEO (title, description, H1–H3, alt, sitemap.xml, robots.txt), перевірка в Chrome/Safari/Firefox і 14 днів підтримки після запуску.",
     3000, "4", "чи є макет у Figma і чи потрібні анімації?"),
    (("інтернет-магазин", "e-commerce", "кошик", "оплата"),
     "Налаштую функціонал інтернет-магазину: товари/категорії, кошик і оформлення, підключення оплати й доставки, базове SEO та коректна робота на мобільних.",
     4000, "5", "на якій платформі магазин і які інтеграції потрібні (оплата, доставка)?"),
]
DEFAULT = ("Готовий виконати ваше завдання під ключ: узгоджуємо ТЗ, роблю поетапно з проміжними показами, після здачі — 14 днів підтримки.",
           3000, "4", "який обсяг робіт і кінцевий термін?")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")


def parse_rss(text):
    root = ET.fromstring(text)
    ch = root.find("channel")
    items = []
    for it in ch.findall("item"):
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "desc": (it.findtext("description") or "").strip(),
            "cats": [(c.text or "").strip() for c in it.findall("category")],
            "guid": (it.findtext("guid") or it.findtext("link") or "").strip(),
        })
    return items


def clean_url(u):
    return u.split("?")[0]


def budget_of(title, desc):
    m = re.search(r"(\d[\d\s]{2,})\s*(UAH|USD|EUR|PLN|грн|\$|₴)", title + " " + desc, re.I)
    return m.group(0).strip() if m else ""


def is_match(it):
    if any(c in WHITELIST_CAT for c in it["cats"]):
        return True
    return bool(TITLE_KW.search(it["title"]))


def _rx(key):
    if re.fullmatch(r"[a-z0-9]+", key):
        return re.compile(r"\b" + re.escape(key) + r"\b")
    return re.compile(r"(?<![a-zа-яіїєґ])" + re.escape(key))


TEMPL_RX = [([_rx(k) for k in keys], b, p, d, q) for keys, b, p, d, q in TEMPL]


def draft_bid(it):
    low = (it["title"] + " " + " ".join(it["cats"]) + " " + it["desc"][:300]).lower()
    body, price, days, q = DEFAULT
    for pats, b, p, d, qq in TEMPL_RX:
        if any(rx.search(low) for rx in pats):
            body, price, days, q = b, p, d, qq
            break
    return (f"Вітаю! Готовий узятися за «{it['title']}».\n\n"
            f"{body}\n\n"
            f"Орієнтовно: {price} ₴, термін {days} дн. Після здачі — 14 днів підтримки.\n"
            f"Портфоліо та приклади: {PORTFOLIO}\n\n"
            f"Уточніть, будь ласка: {q}")


def tg_send(text):
    if not TG_TOKEN:
        return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": text,
                           "disable_web_page_preview": True,
                           "disable_notification": False}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:
        print("tg err:", e)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def scan(record_bids=True):
    seen = set(load_json(SEEN, []))
    bids = load_json(BIDS, {})
    try:
        items = parse_rss(fetch(RSS))
    except Exception as e:
        print("RSS error:", e)
        return 0
    new = [it for it in items if it["guid"] not in seen]
    matches = [it for it in new if is_match(it)]
    for it in items:
        seen.add(it["guid"])
    save_json(SEEN, sorted(seen))
    for it in matches:
        b = budget_of(it["title"], it["desc"])
        url = clean_url(it["link"])
        draft = draft_bid(it)
        head = f"🔥🆕 СВЕЖИЙ ЗАКАЗ{f' | {b}' if b else ''}\n{it['title']}\n{' / '.join(it['cats'])}\n{url}"
        print("=" * 70)
        print(head)
        print("--- черновик ставки ---")
        print(draft)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(head + "\n---\n" + draft + "\n" + "=" * 40 + "\n")
        tg_send(head + "\n\n--- черновик ---\n" + draft)
        if record_bids:
            bids[url] = {"title": it["title"], "budget": b, "draft": draft,
                         "ts": datetime.now().isoformat(timespec="seconds")}
    if record_bids:
        save_json(BIDS, bids)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] новых: {len(new)}, подходящих: {len(matches)}")
    return len(matches)


def show_drafts():
    try:
        items = parse_rss(fetch(RSS))
    except Exception as e:
        print("RSS error:", e)
        return
    m = [it for it in items if is_match(it)]
    print(f"подходящих сейчас: {len(m)}\n")
    for it in m[:8]:
        print("=" * 70)
        print(it["title"], "|", " / ".join(it["cats"]), "|", budget_of(it["title"], it["desc"]))
        print(clean_url(it["link"]))
        print("-" * 70)
        print(draft_bid(it))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0)
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--drafts", action="store_true", help="показать черновики по текущим подходящим")
    ap.add_argument("--state", default="", help="папка для seen/bids/log")
    a = ap.parse_args()
    if a.state:
        set_state_dir(a.state)
    if a.test:
        tg_send("🎯 SNIPER на связи — тестовое сообщение. Новые проекты под наши навыки будут приходить сюда, уже с черновиком ставки.")
        print("test sent")
        return
    if a.drafts:
        show_drafts()
        return
    if a.loop:
        for _ in range(a.loop):
            scan()
            time.sleep(a.interval)
    else:
        scan()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

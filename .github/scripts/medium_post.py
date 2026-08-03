import json
import os
import urllib.request
import xml.etree.ElementTree as ET

FEED = "https://medium.com/feed/@uriy.as59"
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medium_last.json")


def fetch_feed():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (compatible; MediumFeed/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip().split("?")[0]
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            items.append({"title": title, "link": link, "pubDate": pub})
    return items


def send_tg(text):
    token = os.environ["TELEGRAM_TOKEN"]
    chat = os.environ.get("CHAT_ID", "@webstudio_chanel")
    data = json.dumps({"chat_id": chat, "parse_mode": "HTML", "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    items = parse(fetch_feed())
    if not items:
        print("No items in feed")
        return
    latest = items[0]
    try:
        with open(STATE, encoding="utf-8") as f:
            last = json.load(f)
        last_link = last.get("link")
    except Exception:
        last_link = None
    if latest["link"] == last_link:
        print(f"No new articles. Latest: {latest['title']} | {latest['link']}")
        return
    text = (
        f"✍️ <b>{escape(latest['title'])}</b>\n\n"
        f"Новая публикация на Medium — читайте по ссылке:\n"
        f"{latest['link']}\n\n"
        f"📚 Все статьи: https://medium.com/@uriy.as59\n"
        f"🌐 Мы — https://uriy-as.org"
    )
    send_tg(text)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"link": latest["link"], "title": latest["title"], "at": latest["pubDate"]}, f, ensure_ascii=False, indent=2)
    print(f"Posted: {latest['title']} | {latest['link']}")


if __name__ == "__main__":
    main()

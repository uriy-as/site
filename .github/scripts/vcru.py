# -*- coding: utf-8 -*-
"""
Клиент публикации статей на vc.ru (движок Osnova, редактор на Editor.js).

Собирает статью из блоков и отправляет одним запросом в черновик.
Верстка приходит на сайт уже готовой: заголовки, цитаты, разделители,
списки, картинки с подписями, выделения внутри текста.

Авторизация — один из двух способов:
  1. VC_JWT   — заголовок JWTAuthorization из живой сессии браузера
  2. VC_DEVICE_TOKEN — персональный токен из настроек профиля

Оба значения читаются из окружения или из файла credentials проекта.
"""
import json, os, re, urllib.request, urllib.parse, mimetypes, time

API = "https://api.vc.ru"
UA = "mast-app/1.0 (server; Linux/6; ru; 1080x1920)"


class VC:
    def __init__(self, user_id, jwt=None, device_token=None, subsite_id=None):
        self.user_id = int(user_id)
        self.subsite_id = int(subsite_id or user_id)
        self.jwt = jwt or os.environ.get("VC_JWT")
        self.device = device_token or os.environ.get("VC_DEVICE_TOKEN")
        if not (self.jwt or self.device):
            raise RuntimeError("нужен VC_JWT или VC_DEVICE_TOKEN")

    def _headers(self):
        h = {"User-agent": UA, "pwa": "1"}
        if self.jwt:
            h["JWTAuthorization"] = self.jwt if self.jwt.startswith("Bearer ") else "Bearer " + self.jwt
        if self.device:
            h["X-Device-Token"] = self.device
        return h

    def _post_form(self, path, fields):
        boundary = "----vc" + str(int(time.time() * 1000))
        body = b""
        for k, v in fields.items():
            body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode()
        body += ("--%s--\r\n" % boundary).encode()
        h = self._headers()
        h["Content-Type"] = "multipart/form-data; boundary=" + boundary
        req = urllib.request.Request(API + path, data=body, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    # ---------- картинки ----------
    def upload(self, image_url):
        """Загружает картинку по ссылке, возвращает объект для блока media."""
        j = self._post_form("/v2.1/uploader/upload", {"url": image_url})
        d = j["result"][0]["data"]
        return {k: d[k] for k in ("uuid", "width", "height", "size", "type", "color") if k in d}

    # ---------- блоки ----------
    @staticmethod
    def text(html):
        return {"type": "text", "data": {"text": html if html.startswith("<") else "<p>%s</p>" % html}}

    @staticmethod
    def header(text, level=2):
        return {"type": "header", "data": {"style": "h%d" % level, "text": text}}

    @staticmethod
    def quote(text, author=""):
        return {"type": "quote", "data": {"text": text, "subline1": author}}

    @staticmethod
    def delimiter():
        return {"type": "delimiter", "data": {"type": "default"}}

    @staticmethod
    def bullets(items, ordered=False):
        return {"type": "list", "data": {"type": "OL" if ordered else "UL", "items": items}}

    @staticmethod
    def incut(text):
        return {"type": "incut", "data": {"text": text}}

    @staticmethod
    def media(image_obj, caption=""):
        return {"type": "media", "data": {
            "items": [{"title": caption, "image": {"type": "image", "data": image_obj}}],
            "with_border": False, "with_background": False}}

    @staticmethod
    def gallery(image_objs, captions=None):
        caps = captions or [""] * len(image_objs)
        return {"type": "media", "data": {
            "items": [{"title": c, "image": {"type": "image", "data": im}} for im, c in zip(image_objs, caps)],
            "with_border": False, "with_background": False}}

    # ---------- запись ----------
    def save(self, title, blocks, entry_id=None, publish=False):
        """Создает или обновляет запись. publish=False оставляет ее черновиком."""
        entry = {
            "user_id": self.user_id, "type": 1, "subsite_id": self.subsite_id,
            "title": title, "entry": {"blocks": blocks},
            "external_access_link": "", "path": "",
            "is_editorial": False, "is_advertisement": False,
            "is_enabled_comments": True, "is_enabled_likes": True,
            "withheld": False, "is_enabled_ad": True, "is_holdonflash": False,
            "forced_to_mainpage": 0, "is_holdonmain": False,
            "is_published": bool(publish), "is_adult": False,
            "repostId": None, "repostData": None,
        }
        if entry_id:
            entry["id"] = int(entry_id)
        j = self._post_form("/v2.1/editor", {"entry": json.dumps(entry, ensure_ascii=False)})
        e = j["result"]["entry"]
        return {"id": e["id"], "blocks": len(e["entry"]["blocks"]),
                "url": "https://vc.ru/?modal=editor&action=edit&id=%d" % e["id"]}


# ---------- разметка в блоки ----------
def md_to_blocks(md, images=None):
    """
    Превращает упрощенную разметку в блоки vc.ru.
      ## заголовок        -> header h2
      ### заголовок       -> header h3
      > цитата | автор    -> quote
      ---                 -> delimiter
      * пункт             -> list
      !! врезка           -> incut
      [[файл.jpg|подпись]]-> media (images — словарь имя файла: объект от upload)
      **жирный** _курсив_ [текст](ссылка) — внутри абзацев
    """
    images = images or {}
    out, buf, lst = [], [], []

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def inline(s):
        s = esc(s)
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(^|[\s(])_([^_]+)_", r"\1<i>\2</i>", s)
        return s

    def flush_p():
        if buf:
            out.append(VC.text("<p>%s</p>" % inline(" ".join(buf))))
            buf.clear()

    def flush_l():
        if lst:
            out.append(VC.bullets([inline(x) for x in lst]))
            lst.clear()

    for raw in md.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush_p(); flush_l(); continue
        m = re.match(r"^\[\[([^|\]]+)\|?([^\]]*)\]\]$", line.strip())
        if m:
            flush_p(); flush_l()
            im = images.get(m.group(1))
            if im:
                out.append(VC.media(im, m.group(2)))
            continue
        if line.startswith("### "):
            flush_p(); flush_l(); out.append(VC.header(line[4:], 3)); continue
        if line.startswith("## "):
            flush_p(); flush_l(); out.append(VC.header(line[3:], 2)); continue
        if line.startswith("> "):
            flush_p(); flush_l()
            body = line[2:]
            author = ""
            if "|" in body:
                body, author = [x.strip() for x in body.split("|", 1)]
            out.append(VC.quote(body, author)); continue
        if line.strip() == "---":
            flush_p(); flush_l(); out.append(VC.delimiter()); continue
        if line.startswith("!! "):
            flush_p(); flush_l(); out.append(VC.incut(line[3:])); continue
        if line.startswith("* "):
            flush_p(); lst.append(line[2:]); continue
        buf.append(line.strip())
    flush_p(); flush_l()
    return out

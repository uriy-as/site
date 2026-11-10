#!/usr/bin/env python3
"""Sniper для freelance.ua — обгортка над fh_sniper (окремий state, фільтри)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fh_sniper

fh_sniper.RSS = "https://freelance.ua/ru/orders/rss"

fh_sniper.WHITELIST_CAT = {
    "Веб-програмування", "Веб-программирование", "Создание сайтов",
    "Продвижение сайта", "Пошукова оптимізація (SEO)", "Программирование",
    "Разработка CRM и ERP", "Інтернет-магазини", "Збір інформації",
    "Техническая поддержка", "Автоматизація",
}
fh_sniper.EXCLUDE_CAT = {
    "Аудио/Видео", "Видеомонтаж", "Дизайн", "Иллюстрации",
    "SMM", "Продвижение в социальных сетях", "Перевод текстов",
    "Копирайтинг", "Логотипы", "3D", "Дизайн интерфейсов",
}


def set_state_dir(d):
    os.makedirs(d, exist_ok=True)
    fh_sniper.SEEN = os.path.join(d, "fu_sniper_seen.json")
    fh_sniper.LOG = os.path.join(d, "fu_sniper_matches.log")
    fh_sniper.BIDS = os.path.join(d, "fu_sniper_bids.json")


fh_sniper.set_state_dir = set_state_dir


def tg_send(text):
    fh_sniper.tg_send("[Freelance.ua] " + text)


fh_sniper.tg_send = tg_send

if __name__ == "__main__":
    fh_sniper.main()

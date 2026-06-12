# Развёртывание Telegram-бота на PythonAnywhere

## 1. Загрузить файлы

На вкладке **Files** загрузить:
- `bot.py`
- `requirements.txt`

## 2. Установить зависимости

Открыть **Bash console** и выполнить:
```
pip install --user -r requirements.txt
```

## 3. Настроить веб-приложение

- **Web** → **Add a new web app**
- **Manual configuration** → **Python 3.10**
- В **Code** указать путь к `bot.py`
- В **WSGI configuration file** заменить содержимое на:

```python
import sys
path = '/home/твой_логин/.github/scripts'
if path not in sys.path:
    sys.path.append(path)
from bot import app as application
```

## 4. Установить ключ Gemini

В **Web** → **Environment variables** добавить:
```
GEMINI_API_KEY = твой_ключ
```

В `bot.py` заменить `GEMINI_API_KEY = None` на:

```python
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
```

## 5. Reload и настройка webhook

- Нажать **Reload**
- В браузере открыть: `https://твой_логин.pythonanywhere.com/set_webhook?url=https://твой_логин.pythonanywhere.com/8308743016:AAEwu53QB_rwy5Di40YON4NBZA4A6SbgRQ0`
- Должен прийти ответ: `{"ok": true, ...}`

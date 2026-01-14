# Telegram бот для анкеты продавца

Telegram бот на Python и aiogram для сбора анкет от продавцов с последующим одобрением администратором.

## Установка

1. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Настройте конфигурацию:**
   
   Откройте файл `config.py` и заполните следующие данные:
   
   ```python
   BOT_TOKEN = "ваш_токен_от_BotFather"
   ADMIN_ID = 123456789  # Ваш Telegram ID
   ```
   
   - **BOT_TOKEN**: Получите токен у [@BotFather](https://t.me/BotFather) в Telegram
   - **ADMIN_ID**: Узнайте свой Telegram ID через [@userinfobot](https://t.me/userinfobot) или [@getmyid_bot](https://t.me/getmyid_bot)

3. **Запустите бота:**
   ```bash
   python bot.py
   ```

## Альтернативный способ (через переменные окружения)

Вместо редактирования `config.py`, вы можете установить переменные окружения:

**Windows (PowerShell):**
```powershell
$env:BOT_TOKEN="ваш_токен"
$env:ADMIN_ID="123456789"
python bot.py
```

**Windows (CMD):**
```cmd
set BOT_TOKEN=ваш_токен
set ADMIN_ID=123456789
python bot.py
```

**Linux/Mac:**
```bash
export BOT_TOKEN="ваш_токен"
export ADMIN_ID="123456789"
python bot.py
```

## Как работает бот

1. Продавец отправляет `/start` и заполняет анкету
2. После заполнения анкета отправляется администратору
3. Продавец отправляет селфи/видео с материалом и паспортом
4. Администратор одобряет или отклоняет анкету
5. При одобрении продавец указывает адрес и время для доставки
6. Информация о доставке отправляется администратору

## Структура проекта

- `bot.py` - основной файл с логикой бота
- `config.py` - файл конфигурации (не попадает в git)
- `config.example.py` - пример конфигурации
- `requirements.txt` - зависимости Python
- `.gitignore` - файлы, исключённые из git

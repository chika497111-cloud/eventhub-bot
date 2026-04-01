# 🎫 EventHub Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/aiogram-3.x-009688?style=for-the-badge&logo=telegram&logoColor=white" alt="aiogram">
  <img src="https://img.shields.io/badge/SQLite-aiosqlite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License">
</p>

Telegram-бот для управления мероприятиями и регистрации участников.

---

## Возможности

| Функция | Описание |
|---------|----------|
| 📋 Список событий | Пагинированный список предстоящих мероприятий |
| 📌 Карточка события | Название, описание, дата/время, место, свободные места |
| ✅ Регистрация | Регистрация в один клик с подтверждением |
| ⏳ Лист ожидания | Автоматическое продвижение при отмене другим участником |
| 🎟 Мои регистрации | Просмотр и отмена своих регистраций |
| ⚙️ Админ-панель | Создание, редактирование и отмена мероприятий |
| 👥 Управление участниками | Просмотр списка участников и листа ожидания |
| 📢 Рассылка | Отправка сообщений участникам конкретного события |
| 🔔 Уведомления | Автоматические уведомления при отмене события |
| 🕐 Автостатус | Прошедшие события автоматически помечаются как завершённые |

## Структура проекта

```
eventhub-bot/
├── bot.py                 # Точка входа
├── config.py              # BOT_TOKEN, ADMIN_IDS из .env
├── database.py            # aiosqlite — все операции с БД
├── handlers/
│   ├── __init__.py
│   ├── start.py           # /start, /help, главное меню
│   ├── events.py          # Список событий, детали, регистрация/отмена
│   ├── my_events.py       # Регистрации пользователя
│   └── admin.py           # Админ: создание/редактирование/отмена, рассылка
├── keyboards/
│   ├── __init__.py
│   ├── inline.py          # Inline-клавиатуры
│   └── reply.py           # Reply-клавиатуры
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Схема базы данных

```
┌──────────────────────┐     ┌──────────────────────────┐
│       events         │     │     registrations        │
├──────────────────────┤     ├──────────────────────────┤
│ id          INTEGER  │◄──┐ │ id           INTEGER     │
│ title       TEXT     │   │ │ event_id     INTEGER  ───┘
│ description TEXT     │   │ │ user_id      INTEGER     │
│ date        TEXT     │   │ │ username     TEXT         │
│ time        TEXT     │   │ │ registered_at TEXT       │
│ location    TEXT     │   │ │ status       TEXT         │
│ max_participants INT │   │ │  (registered/cancelled/  │
│ photo_id    TEXT     │   │ │   attended/waitlist)     │
│ status      TEXT     │   │ └──────────────────────────┘
│  (active/cancelled/  │   │
│   completed)         │   │ ┌──────────────────────────┐
│ created_at  TEXT     │   │ │      broadcasts          │
└──────────────────────┘   │ ├──────────────────────────┤
                           │ │ id           INTEGER     │
                           └─│ event_id     INTEGER     │
                             │ message      TEXT         │
                             │ sent_at      TEXT         │
                             └──────────────────────────┘
```

## Пользовательский сценарий

```
Пользователь                        Бот
    │                                 │
    │──── /start ────────────────────>│
    │<─── Приветствие + меню ─────────│
    │                                 │
    │──── 📋 События ───────────────>│
    │<─── Список событий (стр.1) ────│
    │                                 │
    │──── [Выбрать событие] ────────>│
    │<─── Карточка события ──────────│
    │                                 │
    │──── ✅ Зарегистрироваться ───>│
    │<─── Подтверждение ─────────────│
    │                                 │
    │──── 🎟 Мои регистрации ──────>│
    │<─── Список регистраций ────────│
    │                                 │
    │──── ❌ Отменить ──────────────>│
    │<─── Регистрация отменена ──────│
    │                                 │
```

## Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone https://github.com/your-username/eventhub-bot.git
cd eventhub-bot

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Настроить переменные окружения
cp .env.example .env
# Отредактируйте .env: добавьте BOT_TOKEN и ADMIN_ID

# 4. Запустить бота
python bot.py
```

## Админ-команды

| Команда | Описание |
|---------|----------|
| ⚙️ Админ-панель | Открыть панель администратора |
| ➕ Создать событие | Пошаговое создание мероприятия (FSM) |
| ✏️ Редактировать | Изменить поля существующего события |
| 🚫 Отменить событие | Отмена с уведомлением всех участников |
| 👥 Участники | Просмотр списка участников и листа ожидания |
| 📢 Рассылка | Отправка сообщения участникам события |

> Для получения прав администратора добавьте свой Telegram ID в переменную `ADMIN_ID` в файле `.env`. Можно указать несколько ID через запятую.

## Лицензия

MIT License. Copyright (c) 2026 Freeland.

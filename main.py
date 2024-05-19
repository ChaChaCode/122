import logging
from datetime import datetime, timedelta
import sys
from urllib.parse import quote_plus, urlparse, parse_qs, urlunparse
import aiohttp
import asyncio
import hashlib
import re
import io
import requests
from aiogram.types import CallbackQuery
from aiogram.types.web_app_info import WebAppInfo
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from googletrans import Translator
from bs4 import BeautifulSoup
from telethon.tl.types import Channel, Message
from aiogram.utils.exceptions import RetryAfter, ChatNotFound, BotBlocked, UserDeactivated, ChatAdminRequired, \
    BadRequest, MessageToDeleteNotFound
from telethon.sync import TelegramClient
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from aiohttp import ClientSession, ClientTimeout, ClientError
from loguru import logger

from PIL import Image
import sqlite3
import aiogram
import random
import string

from telethon.errors import FloodWaitError, AuthKeyUnregisteredError
import openpyxl
import tempfile


logging.basicConfig(level=logging.INFO)

translator = Translator()

start_date = datetime.now()
yesterday = datetime.now() - timedelta(days=1)

# Токены для бота и API Telegram
BOT_TOKEN = "7018842306:AAGCJZXS98HB85dVYTu1Apyr5Q2lWcaN1kE"
VK_ACCESS_TOKEN = 'a4e86edea4e86edea4e86edeeba7ff283aaa4e8a4e86edec125d5322b959b7255f8d0e5'
YOUTUBE_API_KEY = 'AIzaSyCCsvN5SlVqyUbkWfTFve-3Z4dX8Wl7vwk'
YOUR_CSE_ID = '26a28bb54345d4d87'

api_id = 22779709
api_hash = '15a6b8ad9c9d2699047c9168509aeeb2'
session_file_name = 'moxy'  # Путь к файлу сессии

CHANNEL_ID = '@Shmox1337'  # ID вашего канала

# ID администратора
ADMIN_ID = 5429082466

# Инициализация бота, диспетчера и хранилища
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

logger.remove()
logger.add(sys.stderr, level="INFO")

sent_telegraph_links = set()

# Глобальное хранилище для управления задачами поиска
search_tasks = {}

# В глобальной области видимости добавляем множество для хранения уже отправленных постов
sent_posts = set()

user_ids = set()

# Глобальное хранилище пользователей (замените user_ids на user_data)
user_data = {}

# Глобальное хранилище приложений пользователя
user_apps = {}

# Словарь для отслеживания времени последней активности пользователей
active_users = {}


class Form(StatesGroup):
    vk_search = State()  # State for VK search
    instagram_search = State()  # State for Instagram search
    sending_links = State()  # State for sending links
    showing_more_posts = State()  # State for showing more posts
    waiting_for_browser_search = State()
    yandex_browser_search = State()  # Add this for Yandex Browser search
    global_search = State()  # Новое состояние для глобального поиска
    vk_search_type = State()  # Новое состояние для выбора типа поиска ВК
    vk_pars_search = State()  # State for VK parsing search
    vk_account_parse = State()
    vk_parse = State()

class MyStates(StatesGroup):
    waiting_for_keyword = State()
    waiting_for_telegram_publics_keyword = State()  # State for Telegram publics search
    waiting_for_telegraph_keyword = State()  # State for Telegraph search
    sending_links = State()
    offset = State()
    waiting_for_youtube_search = State()  # State for YouTube search
    waiting_for_next_page = State()
    waiting_for_browser_search = State()
    choosing_time_period = State()  # New state for choosing the search time period
    waiting_for_google_search_keyword = State()  # Новое состояние для поиска Google
    sent_message_ids = []  # Список для хранения ID отправленных сообщений


class YoutubeSearchState(StatesGroup):
    searching = State()  # Состояние поиска видео на YouTube
    next_page_token = State()  # Токен для получения следующей страницы результатов


class SearchType(StatesGroup):
    choosing_search_type = State()  # Состояние выбора типа поиска
    choosing_google_search_type = State()  # Новое состояние для выбора типа поиска в Google
    choosing_year = State()  # Добавляем состояние для выбора года


# Дополнительный класс состояния для пагинации
class InstagramSearch(StatesGroup):
    showing_results = State()


# Новые состояния для пагинации и подтверждения
class InstagramPagination(StatesGroup):
    showing_results = State()
    confirm_continuation = State()


class SearchStates(StatesGroup):
    waiting_for_browser_search = State()
    choosing_my_apps = State()
    choosing_time_period = State()  # Ensure this line is added correctly
    choosing_year = State()

class AddPromoStates(StatesGroup):
    addpromo_count = State()  # Состояние для количества промокодов
    addpromo_amount = State()  # Состояние для количества запросов для промокода

# Предположим, ваш exclusion_list теперь содержит регулярные выражения
exclusion_list = [
    "files.fm",
    "YztOEovieQIzZjY8",
    "DELETED",
    "@mdisk_movie_search_robot",
    "@jugaadlife",
    "@exploits",
    "https://t.me/SLlV_INTIM_BOT",
    "🛑 👉🏻👉🏻👉🏻 ИНФОРМАЦИЯ ДОСТУПНА ЗДЕСЬ ЖМИТЕ 👈🏻👈🏻👈🏻",
    "➡➡➡ KLICKEN HIER!",
    "👉🏻👉🏻👉🏻 WSZYSTKIE INFORMACJE DOSTĘPNE TUTAJ KLIKNIJ👈🏻👈🏻👈🏻",
    "🔞 KLIKNIJ TUTAJ, ABY UZYSKAĆ WIĘCEJ INFORMACJI 👈🏻👈🏻👈🏻",
    "🛑 👉🏻👉🏻👉🏻",
    "https://t.me/spacemalware",
    "https://t.me/OneTelegramSpy_bot",
    # Добавим регулярное выражение для "красных" URL как пример
    r"https?://(?:www\.)?example\.com/banned_content"
]


@dp.message_handler(commands=['userlist'], state="*")
async def show_users_count(message: types.Message):
    count = len(user_data)  # Получаем количество уникальных пользователей
    # Отправляем сообщение с количеством пользователей и кнопкой для показа списка
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Показать список пользователей", callback_data="show_user_list"))
    await message.answer(f"Текущее количество пользователей, использующих бота: {count}", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == 'show_user_list', state="*")
async def show_user_list(callback_query: types.CallbackQuery):
    # Создаем список пользователей с их ID и именами
    user_list = "\n".join(f"ID: {user_id} - Имя: {user_name}" for user_id, user_name in sorted(user_data.items()))
    await callback_query.message.answer(f"Список пользователей:\n{user_list}")
    await callback_query.answer()  # Убираем "часики" на кнопке


async def show_notification(message: types.Message):
    try:
        await bot.send_message(
            message.chat.id,
            text='Вы не подписались!',
            parse_mode='MarkdownV2',
        )
    except Exception as e:
        logger.error(f"Произошла ошибка при отправке уведомления: {e}")


async def on_process_message(message: types.Message):
    user_id = message.from_user.id
    try:
        status = await bot.get_chat_member(CHANNEL_ID, user_id)
        # Если пользователь не подписан
        if status.status not in ["member", "administrator", "creator"]:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}"))
            keyboard.add(InlineKeyboardButton("Я подписался(лась)", callback_data="check_subscription"))

            if message is not None:  # Проверяем, доступно ли сообщение
                await message.answer(
                    "Чтобы продолжить использование бота, пожалуйста, подпишитесь на канал и нажмите кнопку ниже:",
                    reply_markup=keyboard
                )
            raise CancelHandler()
    except (ChatNotFound, BotBlocked, UserDeactivated, ChatAdminRequired, BadRequest) as e:
        logger.error(f"Subscription check failed: {e}")
        if message is not None:  # Проверяем, доступно ли сообщение
            await show_notification(message)
        raise CancelHandler()


class SubscriptionMiddleware(BaseMiddleware):
    pass


dp.middleware.setup(SubscriptionMiddleware())


async def check_subscription(message: types.Message) -> bool:
    user_id = message.from_user.id
    try:
        status = await bot.get_chat_member(CHANNEL_ID, user_id)
        # Проверяем, что пользователь подписан на канал
        return status and status.status not in ["left", "kicked"]
    except (ChatNotFound, BotBlocked, UserDeactivated, ChatAdminRequired, BadRequest):
        return False


@dp.callback_query_handler(lambda c: c.data == 'check_subscription', state="*")
async def process_check_subscription_callback(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    try:
        member_status = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member_status.status in ["member", "administrator", "creator"]:
            await start(callback_query.message, state)  # Перезапуск бота
        else:
            await callback_query.answer("Вы не подписались!")
            # Отправить повторно кнопки подписки, если пользователь все еще не подписан
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}"))
            keyboard.add(InlineKeyboardButton("Я подписался(лась)", callback_data="check_subscription"))
            await callback_query.message.edit_text(
                "Чтобы продолжить использование бота, пожалуйста, подпишитесь на канал и нажмите кнопку ниже:",
                reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Subscription check failed: {e}")
        # Правильный вызов метода show_notification
        await show_notification(callback_query.message)


def update_user_activity(user_id):
    if user_id != 5429082466:  # Замените BOT_ID на фактический идентификатор вашего бота
        active_users[user_id] = datetime.now()


def get_online_users_count():
    five_minutes_ago = datetime.now() - timedelta(minutes=60)
    return sum(1 for last_active in active_users.values() if last_active > five_minutes_ago)

# Создаем базу данных и таблицу
conn = sqlite3.connect('subscriptions.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                  user_id INTEGER PRIMARY KEY,
                  subscription_type TEXT,
                  subscription_expiry TEXT,
                  daily_request_limit INTEGER
               )''')

conn.commit()
conn.close()


def add_user(user_id, subscription_type, subscription_expiry, daily_request_limit):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()

    cursor.execute('''INSERT INTO users (user_id, subscription_type, subscription_expiry, daily_request_limit)
                      VALUES (?, ?, ?, ?)''', (user_id, subscription_type, subscription_expiry, daily_request_limit))

    conn.commit()
    conn.close()


def get_subscription(user_id):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()

    cursor.execute('''SELECT subscription_type, subscription_expiry, daily_request_limit 
                      FROM users WHERE user_id=?''', (user_id,))

    subscription_info = cursor.fetchone()

    conn.close()

    return subscription_info


# Создаем базу данных и таблицы
conn = sqlite3.connect('subscriptions.db')
cursor = conn.cursor()

# Создаем таблицу пользователей
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                  user_id INTEGER PRIMARY KEY,
                  subscription_type TEXT,
                  subscription_expiry TEXT,
                  daily_request_limit INTEGER
               )''')

# Создаем таблицу промокодов
cursor.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
                  promo_code TEXT PRIMARY KEY,
                  user_id INTEGER,
                  amount INTEGER
               )''')

# Создаем таблицу для отслеживания предоставленных бонусных запросов для пользователей с уровнем подписки "Beta"
cursor.execute('''CREATE TABLE IF NOT EXISTS beta_granted_requests (
                  user_id INTEGER PRIMARY KEY,
                  granted_requests INTEGER
               )''')

conn.commit()
conn.close()

# Инициализация базы данных
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Создание таблицы для пользователей с добавлением столбца user_username
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (id INTEGER PRIMARY KEY, user_id INTEGER, user_name TEXT, user_username TEXT)''')
conn.commit()

@dp.message_handler(commands=['start'], state="*")
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_name = message.from_user.full_name  # Получаем полное имя пользователя
    user_username = message.from_user.username  # Получаем username пользователя, если есть
    user_data[user_id] = user_name  # Сохраняем или обновляем имя пользователя в словаре
    update_user_activity(user_id)  # Добавляем пользователя в счетчик онлайн
    online_users_count = get_online_users_count()  # Получаем количество онлайн пользователей
    # Проверка наличия пользователя в базе данных
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    existing_user = cursor.fetchone()
    if existing_user is None:
        # Запись нового пользователя в базу данных
        cursor.execute("INSERT INTO users (user_id, user_name, user_username) VALUES (?, ?, ?)", (user_id, user_name, user_username))
        conn.commit()
    await state.reset_state()  # Очищаем любое существующее состояние, обеспечивая чистое управление состоянием.
    if await check_subscription(message):
        # Пользователь подписан; показать опции.
        welcome_text = f"*Текущий онлайн: {online_users_count}\nВыберите место, где хотите произвести поиск:*"
        keyboard = InlineKeyboardMarkup(row_width=2)
        buttons = [
            InlineKeyboardButton("Вконтакте 😊", callback_data="vk_search_type"),
            InlineKeyboardButton("Инстаграм 📸", callback_data="instagram"),
            InlineKeyboardButton("YouTube 🎥", callback_data="youtube"),
            InlineKeyboardButton("Google 🌐", callback_data="google_search"),
            InlineKeyboardButton("Telegraph 📲", callback_data="telegraph"),
            InlineKeyboardButton("Тг Паблики 📢", callback_data="telegram_publics"),
            InlineKeyboardButton('Нейросеть 🧠',
                                 web_app=WebAppInfo(url='https://perchance.org/fusion-ai-image-generator')),
            InlineKeyboardButton("➕ приложение 📱", callback_data="websearch"),
            InlineKeyboardButton("Личный кабинет 👤", callback_data="personal_cabinet")
        ]

        keyboard.add(*buttons)
        # Отправляем фото с клавиатурой
        await message.answer_photo(photo=open("Frame 14.png", "rb"),
                                   caption=welcome_text,
                                   reply_markup=keyboard,
                                   parse_mode="Markdown",
                                   disable_notification=True)
    else:
        # Пользователь не подписан; предложите подписаться.
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("*Подписаться на канал*", url=f"https://t.me/Shmox1337"))
        await message.answer("Чтобы продолжить использование бота, пожалуйста, подпишитесь на наш канал:",
                             reply_markup=keyboard)

# Обработчик команды /users
@dp.message_handler(commands=['users'])
async def users_list(message: types.Message):
    # Проверка, что запрос отправлен администратором
    if message.from_user.id != ADMIN_ID:
        await message.reply("Эта команда доступна только администратору.")
        return

    # Получение списка всех пользователей из базы данных
    cursor.execute("SELECT user_id, user_name, user_username FROM users")
    users = cursor.fetchall()

    # Формирование текста для вывода
    text = "Список пользователей:\n"
    for user in users:
        text += f"ID: {user[0]}, Имя: {user[1]}, Username: @{user[2]}\n"

    # Запись списка пользователей в файл с использованием UTF-8
    with open("users_list.txt", "w", encoding="utf-8") as file:
        file.write(text)

    # Отправка файла пользователю
    with open("users_list.txt", "rb") as file:
        await message.answer_document(file, caption="Список пользователей")



# Команда /help
@dp.message_handler(commands=['help'], state="*")
async def help_command(message: types.Message):
    help_text = """```
*Инструкция по поиску постов:*
1. Нажмите на нужную вам соцсеть.
2. Напишите ключевое слово, которое вы хотите найти в посте.
3. Отправьте сообщение и ожидайте ответа от бота.

*Инструкция по добавлению веб-приложения (сайта):*
1. Нажмите на кнопку "+ приложение".
2. Скиньте ссылку на сайт, который вы хотите добавить.  
3. Вам будет предложено выбрать один из вариантов:
    открыть его для просмотра, добавить в свои 
    приложения или вернуться назад.      
4. Если вы выберете "добавить приложение",
    оно сохранится в вашем личном кабинете в разделе
    "приложения".```
    """

    await message.answer(help_text, parse_mode="Markdown")

# Обработчик главного меню
@dp.message_handler(lambda message: message.text == "Меню", state="*")
async def show_menu(message: types.Message):
    # Обновляем активность пользователя и добавляем его в счетчик онлайна
    update_user_activity(message.from_user.id)

    # Текст и клавиатура главного меню
    welcome_text = "*Вы в главном меню. Выберите, что хотите сделать:*"
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("Вконтакте 😊", callback_data="vk_search_type"),
        InlineKeyboardButton("Инстаграм 📸", callback_data="instagram"),
        InlineKeyboardButton("YouTube 🎥", callback_data="youtube"),
        InlineKeyboardButton("Google 🌐", callback_data="google_search"),
        InlineKeyboardButton("Telegraph 📲", callback_data="telegraph"),
        InlineKeyboardButton("Тг Паблики 📢", callback_data="telegram_publics"),
        InlineKeyboardButton('Нейросеть 🧠',
                             web_app=WebAppInfo(url='https://perchance.org/fusion-ai-image-generator')),
        InlineKeyboardButton("➕ приложение 📱", callback_data="websearch"),
        InlineKeyboardButton("Личный кабинет 👤", callback_data="personal_cabinet")
    ]

    keyboard.add(*buttons)

    # Отправка сообщения с фотографией и клавиатурой
    with open("Frame 14.png", "rb") as photo:
        await message.answer_photo(photo=photo, caption=welcome_text, reply_markup=keyboard, parse_mode="Markdown",
                                   disable_notification=True)


# Функция для обновления подписки пользователя
def update_subscription(user_id, subscription_type, subscription_expiry, daily_request_limit):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()

    cursor.execute('''UPDATE users 
                      SET subscription_type=?, subscription_expiry=?, daily_request_limit=?
                      WHERE user_id=?''', (subscription_type, subscription_expiry, daily_request_limit, user_id))

    conn.commit()
    conn.close()


def update_request_limit(user_id):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()

    # Получаем текущее значение лимита запросов
    cursor.execute('''SELECT daily_request_limit FROM users WHERE user_id=?''', (user_id,))
    current_limit = cursor.fetchone()[0]

    # Проверяем, не достигнуто ли значение лимита запросов
    if current_limit > 0:
        # Уменьшаем на 1 значение daily_request_limit для данного пользователя
        cursor.execute('''UPDATE users SET daily_request_limit = daily_request_limit - 0.5 WHERE user_id=?''', (user_id,))
        conn.commit()
        conn.close()
        return True  # Успешно уменьшили лимит запросов
    else:
        conn.close()
        return False  # Лимит запросов уже достигнут

# Функция для генерации промокода с заданным количеством дополнительных запросов
def generate_promo_code(amount):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()

    # Генерируем уникальный промокод
    promo_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Сохраняем промокод в базе данных
    cursor.execute('''INSERT INTO promo_codes (promo_code, amount) VALUES (?, ?)''', (promo_code, amount))

    conn.commit()
    conn.close()

    return promo_code

# Функция для использования промокода
def use_promo_code(user_id, promo_code):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()

    # Проверяем, существует ли промокод и он не использован
    cursor.execute('''SELECT amount FROM promo_codes WHERE promo_code=? AND user_id IS NULL''', (promo_code,))
    promo_info = cursor.fetchone()

    if promo_info:
        amount = promo_info[0]
        # Обновляем лимит запросов для пользователя
        cursor.execute('''UPDATE users SET daily_request_limit = daily_request_limit + ? WHERE user_id=?''', (amount, user_id))
        # Устанавливаем владельца промокода
        cursor.execute('''UPDATE promo_codes SET user_id=? WHERE promo_code=?''', (user_id, promo_code))
        conn.commit()
        conn.close()
        return f"Промокод успешно использован. Вам добавлено {amount} запросов."
    else:
        conn.close()
        return "Промокод недействителен или уже использован."


# Обработчик команды /addpromo для администратора
@dp.message_handler(commands=['addpromo'], state="*")
async def generate_promo_code_admin(message: types.Message):
    # Проверяем, является ли отправитель администратором
    if message.from_user.id == 5429082466:
        await message.answer("Сначала укажите количество промокодов, а затем количество запросов для каждого промокода, через пробел.\nНапример: 5 10")
        # Устанавливаем состояние, чтобы следующее сообщение обрабатывалось как количество промокодов и запросов для каждого промокода
        await AddPromoStates.addpromo_count.set()
    else:
        await message.answer("Эта команда доступна только администраторам.")

# Обработчик текстового сообщения с количеством промокодов и запросов для каждого промокода
# Обработчик текстового сообщения с количеством промокодов и запросов для каждого промокода
@dp.message_handler(state=AddPromoStates.addpromo_count)
async def set_addpromo_count(message: types.Message, state: FSMContext):
    try:
        # Разделяем текст сообщения на количество промокодов и количество запросов для каждого промокода
        count, amount = map(int, message.text.split())
        if count <= 0 or amount <= 0:
            await message.answer("Количество промокодов и количество запросов должны быть больше нуля. Пожалуйста, попробуйте еще раз.")
            return

        # Генерируем указанное количество промокодов с указанным количеством запросов
        promo_codes = [generate_promo_code(amount) for _ in range(count)]
        # Форматируем промокоды для вставки в сообщение
        promo_codes_formatted = '\n'.join([f'<code>{code}</code>' for code in promo_codes])
        # Отправляем промокоды с использованием HTML разметки для стилизации текста как блока кода
        await message.answer(promo_codes_formatted, parse_mode="HTML")

        # Сбрасываем состояние
        await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите целые числа через пробел.")


# Обработчик текстового сообщения с количеством запросов для промокода
@dp.message_handler(state=AddPromoStates.addpromo_amount)
async def set_addpromo_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            await message.answer("Количество запросов должно быть больше нуля. Пожалуйста, попробуйте еще раз.")
            return

        # Получаем количество промокодов из состояния
        data = await state.get_data()
        addpromo_count = data.get('addpromo_count')

        # Генерируем указанное количество промокодов с указанным количеством запросов
        for _ in range(addpromo_count):
            generate_promo_code(amount)

        await message.answer(f"Сгенерировано {addpromo_count} промокодов на {amount} запросов.")

        # Сбрасываем состояние
        await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")

# Обработчик команды /promo для пользователей
@dp.message_handler(commands=['promo'], state="*")
async def start_promo(message: types.Message, state: FSMContext):
    await message.answer("Напишите промокод.")
    # Устанавливаем состояние ожидания промокода
    await state.set_state("waiting_code")

# Обработчик текстового сообщения с промокодом
@dp.message_handler(state="waiting_code", content_types=types.ContentType.TEXT)
async def handle_promo_message(message: types.Message, state: FSMContext):
    # Получаем промокод из сообщения
    promo_code = message.text.upper()  # Промокоды нечувствительны к регистру

    # В противном случае, обрабатываем промокод
    response = use_promo_code(message.from_user.id, promo_code)
    await message.answer(response)
    # Сбрасываем состояние
    await state.finish()



@dp.callback_query_handler(lambda query: query.data == "personal_cabinet", state="*")
async def show_personal_cabinet(callback_query: types.CallbackQuery, state: FSMContext):
    # Удаляем предыдущее сообщение с запросом ключевого слова
    await callback_query.message.delete()

    user_id = callback_query.from_user.id
    user_name = callback_query.from_user.full_name
    user_subscription_level = get_subscription_level(user_id)
    remaining_requests = get_remaining_requests(user_id)  # Получаем оставшиеся запросы
    cabinet_text = f"Личный кабинет {user_name}\nОсталось запросов: {remaining_requests}🔎"
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Магазин 🔎", callback_data="subscription"),
        InlineKeyboardButton("Мои Приложения 📱", callback_data="my_apps"),
        InlineKeyboardButton("Поддержка 🤝", url="https://t.me/Shmoxy"),
        InlineKeyboardButton("Назад ↩️", callback_data="back_so_kabinet")
    )
    await callback_query.message.answer(cabinet_text, reply_markup=keyboard)

    await state.finish()


def get_remaining_requests(user_id):
    # Получаем информацию о подписке пользователя из базы данных
    subscription_info = get_subscription(user_id)
    if subscription_info:
        subscription_type, _, daily_request_limit = subscription_info
        # Определяем, сколько запросов осталось сегодня
        remaining_requests = calculate_remaining_requests(user_id, subscription_type, daily_request_limit)
        return remaining_requests
    else:
        return "Без подписки"


def calculate_remaining_requests(user_id, subscription_type, daily_request_limit):
    # Здесь нужно реализовать логику расчета оставшихся запросов в зависимости от уровня подписки
    # Пока просто вернем daily_request_limit
    return daily_request_limit


def get_subscription_level(user_id):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()

    cursor.execute('''SELECT subscription_type FROM users WHERE user_id=?''', (user_id,))
    subscription_info = cursor.fetchone()

    if subscription_info:
        subscription_type = subscription_info[0]
        # Проверяем, есть ли уже предоставленные бонусные запросы для пользователя с уровнем подписки "Beta"
        cursor.execute('''SELECT granted_requests FROM beta_granted_requests WHERE user_id=?''', (user_id,))
        granted_requests = cursor.fetchone()
        if subscription_type == "Beta" and not granted_requests:
            # Добавляем бонусные запросы и отмечаем, что они предоставлены
            cursor.execute('''INSERT INTO beta_granted_requests (user_id, granted_requests) VALUES (?, ?)''', (user_id, 1))
            conn.commit()
            # Добавляем 5 запросов пользователю с уровнем подписки "Beta"
            cursor.execute('''UPDATE users SET daily_request_limit = daily_request_limit + 5 WHERE user_id=?''', (user_id,))
            conn.commit()
        conn.close()
        return subscription_type
    else:
        # Если у пользователя нет подписки, выдаем ему Beta подписку с 5 дополнительными запросами
        add_user(user_id, 'Beta', '', 5)
        conn.close()
        return "Beta"


# Словарь цен на подписки
subscription_prices = {
    "watson": 230,
    "sherlock": 430,
    "FBI": 1830,
    "Beta": "Недоступно"
}

@dp.callback_query_handler(lambda query: query.data == "subscription", state="*")
async def handle_subscription(callback_query: types.CallbackQuery):
    # Удаляем предыдущее сообщение с запросом ключевого слова
    await callback_query.message.delete()

    user_name = callback_query.from_user.full_name
    message_text = f"{user_name}. Выберите количество запросов для покупки."

    keyboard = InlineKeyboardMarkup(row_width=1)
    buttons = [
        InlineKeyboardButton("50🔎 - 230 руб", callback_data="subscribe_watson"),
        InlineKeyboardButton("100🔎 - 430 руб", callback_data="subscribe_sherlock"),
        InlineKeyboardButton("500🔎 - 1830 руб", callback_data="subscribe_FBI"),
        InlineKeyboardButton("Назад ↩️", callback_data="personal_cabinet")
    ]
    keyboard.add(*buttons)

    await callback_query.message.answer(message_text, reply_markup=keyboard)


@dp.callback_query_handler(lambda query: query.data.startswith("subscribe_"), state="*")
async def handle_subscribe(callback_query: types.CallbackQuery):
    subscription_type = callback_query.data.split("_")[1]

    # Удаляем предыдущее сообщение с запросом подписки
    await callback_query.message.delete()

    # Получаем цену подписки из словаря цен
    price = subscription_prices.get(subscription_type, "Цена не найдена")

    # Допустим, здесь будет логика обработки подписки
    subscription_descriptions = {
        "watson": "Подписка Ватсон дает 50🔎 запросов.",
        "sherlock": "Подписка Шерлок дает 100🔎 запросов.",
        "FBI": "Подписка FBI дает 500🔎 запросов.",
    }

    description = subscription_descriptions.get(subscription_type, "Нет описания")

    # Определение пути к файлу изображения
    image_paths = {
        "watson": "OIG1 (2).jpg",
        "sherlock": "OIG1 (1).jpg",
        "FBI": "OIG2.jpg"
    }
    image_path = image_paths.get(subscription_type)

    # Создаем клавиатуру с кнопками оформления покупки и кнопкой назад (если это не Beta подписка)
    keyboard = InlineKeyboardMarkup(row_width=1)
    if subscription_type != "Beta":
        keyboard.add(
            InlineKeyboardButton(f"Оформить покупку",
                                 callback_data=f"purchase_{subscription_type}_{price}"),
        )
    keyboard.add(
        InlineKeyboardButton("Назад", callback_data="subscription")
    )

    # Отправляем сообщение с изображением, описанием подписки и кнопкой оформления покупки (если это не Beta подписка)
    with open(image_path, "rb") as photo:
        caption = f"Вы выбрали покупку {subscription_type.capitalize()}.\n\n{description}"
        await callback_query.message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=keyboard
        )

def update_requests_after_purchase(user_id, subscription_type):
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()

    # Получаем количество запросов, добавляемых с этой подпиской
    additional_requests = get_additional_requests_for_subscription(subscription_type)

    # Обновляем количество доступных запросов для пользователя
    cursor.execute('''UPDATE users SET daily_request_limit = daily_request_limit + ? WHERE user_id=?''',
                   (additional_requests, user_id))
    conn.commit()
    conn.close()

def get_additional_requests_for_subscription(subscription_type):
    additional_requests_map = {
        "watson": 50,
        "sherlock": 100,
        "FBI": 500
    }
    return additional_requests_map.get(subscription_type, 0)
@dp.callback_query_handler(lambda query: query.data.startswith("purchase_"), state="*")
async def handle_purchase(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    try:
        # Разбиваем данные callback_query для получения типа подписки и цены
        subscription_data = callback_query.data.split("_")
        subscription_type = subscription_data[1]
        price = subscription_data[2]

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text='Оплатить', pay=True))
        markup.add(types.InlineKeyboardButton("Назад", callback_data="subscription"))

        await bot.send_invoice(
            chat_id=callback_query.message.chat.id,
            title='Информация',
            description=f'Оплата за подписку {subscription_type.capitalize()} - {price} рублей в Юкассе',
            payload=f"Подписка_{subscription_type}_{price}",  # Передаем информацию о подписке и цене в payload
            provider_token='390540012:LIVE:50832',
            start_parameter='drive_Booking',
            currency='RUB',
            prices=[types.LabeledPrice(label=f"Подписка {subscription_type.capitalize()}", amount=int(price) * 100)],
            reply_markup=markup
        )

    except Exception as e:
        logging.exception(f"Произошла ошибка: {str(e)}")
        await bot.send_message(callback_query.message.chat.id, str(e))

@dp.pre_checkout_query_handler(lambda query: True)
async def process_pre_checkout_query(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def got_payment(message: types.Message):
    try:
        invoice_payload = message.successful_payment.invoice_payload
        user_info = f"Данные платежа: {invoice_payload}"
        await message.answer("Платеж успешно проведен. " + user_info)

        # Получаем информацию о подписке из payload
        subscription_info = message.successful_payment.invoice_payload.split("_")[1]

        # Обновляем количество доступных запросов после покупки подписки
        update_requests_after_purchase(message.from_user.id, subscription_info)

        # Отправляем пользователя в главное меню
        await show_menu(message)

    except Exception as e:
        logging.exception(f"Произошла ошибка при обработке успешного платежа: {str(e)}")
        await message.answer("Произошла ошибка при обработке успешного платежа. Пожалуйста, свяжитесь с поддержкой.")



def create_table():
    conn = sqlite3.connect('user_apps.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_apps
                 (user_id INTEGER, app_url TEXT)''')
    conn.commit()
    conn.close()


# Функция для добавления приложения пользователя в базу данных
def add_app_to_db(user_id, app_url):
    conn = sqlite3.connect('user_apps.db')
    c = conn.cursor()
    c.execute("INSERT INTO user_apps VALUES (?, ?)", (user_id, app_url))
    conn.commit()
    conn.close()


# Функция для получения списка приложений пользователя из базы данных
def get_user_apps(user_id):
    conn = sqlite3.connect('user_apps.db')
    c = conn.cursor()
    c.execute("SELECT app_url FROM user_apps WHERE user_id=?", (user_id,))
    apps = c.fetchall()
    conn.close()
    return [app[0] for app in apps]


# Функция для удаления приложения пользователя из базы данных
def delete_app_from_db(user_id, app_url):
    conn = sqlite3.connect('user_apps.db')
    c = conn.cursor()
    c.execute("DELETE FROM user_apps WHERE user_id=? AND app_url=?", (user_id, app_url))
    conn.commit()
    conn.close()


# Вызываем функцию create_table() один раз перед использованием базы данных
create_table()


# Обработчик кнопки "Добавить в мои приложения" для поиска в веб-приложении
@dp.callback_query_handler(lambda c: c.data == 'add_to_my_apps_web', state="*")
async def add_to_my_apps_web(callback_query: types.CallbackQuery, state: FSMContext):
    outer_user_data = await state.get_data()
    user_link = outer_user_data.get('url')

    if user_link:
        user_id = callback_query.from_user.id
        apps_list = get_user_apps(user_id)
        if user_link in apps_list:
            await callback_query.answer('Это приложение уже добавлено!')
        else:
            add_app_to_db(user_id, user_link)
            await show_personal_cabinet(callback_query, state)
            update_request_limit(user_id)
            update_request_limit(user_id)
            update_request_limit(user_id)
            update_request_limit(user_id)
            update_request_limit(user_id)
            update_request_limit(user_id)
            await callback_query.answer('Сайт добавлен в ваши приложения!')
    await state.finish()


# Обработчик кнопки "Добавить в мои приложения" для поиска в обычном вводе ссылки
@dp.callback_query_handler(lambda c: c.data == 'add_to_my_apps', state="*")
async def add_to_my_apps(callback_query: types.CallbackQuery, state: FSMContext):
    outer_user_data = await state.get_data()
    user_link = outer_user_data.get('url')

    if user_link:
        user_id = callback_query.from_user.id
        apps_list = get_user_apps(user_id)
        if user_link in apps_list:
            await callback_query.answer('Это приложение уже добавлено!')
        else:
            add_app_to_db(user_id, user_link)
            await callback_query.answer('Сайт добавлен в ваши приложения!')
            update_request_limit(user_id)
            update_request_limit(user_id)
            update_request_limit(user_id)
            update_request_limit(user_id)
            update_request_limit(user_id)
            update_request_limit(user_id)
            if callback_query.message:
                await bot.delete_message(chat_id=callback_query.message.chat.id,
                                         message_id=callback_query.message.message_id)
    else:
        await callback_query.answer('Вы уже добавили его!')
    await state.finish()


# Обработчик нажатия кнопки "Добавить веб-поиск"
@dp.callback_query_handler(text_startswith="addwebsearch")
async def process_websearch_button(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    await callback_query.answer(text="", show_alert=True)  # Добавление этой строки

    message_to_delete = await callback_query.message.answer(
        "-3🔎 Скиньте ссылку на сайт, чтобы открыть его в веб-приложении:")
    await state.update_data(message_to_delete_id=message_to_delete.message_id)

    # Устанавливаем состояние для обработчика ссылок из веб-поиска
    await state.set_state("addwebsearch")


# Обработчик нажатия кнопки "Веб-поиск"
@dp.callback_query_handler(text_startswith="websearch")
async def process_websearch_button(callback_query: types.CallbackQuery, state: FSMContext):
    # Убираем свечение
    await callback_query.answer()

    message_to_delete = await callback_query.message.answer(
        "-3🔎 Скиньте ссылку на сайт, чтобы открыть его в веб-приложении:")
    await state.update_data(message_to_delete_id=message_to_delete.message_id)

    # Устанавливаем состояние для обработчика ссылок из обычного ввода
    await state.set_state("websearch")


# Обработчик сообщений для добавления ссылок из веб-поиска
@dp.message_handler(state="addwebsearch", content_types=types.ContentType.TEXT)
async def receive_link_addweb(message: types.Message, state: FSMContext):
    user_link = message.text
    # Проверка на наличие ссылки
    if not user_link.startswith("http"):
        await message.delete()
        return
    domain_name = urlparse(user_link).netloc
    button_text = domain_name if domain_name else user_link
    button = InlineKeyboardButton(button_text, web_app=WebAppInfo(url=user_link))
    keyboard = InlineKeyboardMarkup().add(button)
    await state.update_data(url=user_link)

    add_app_button = InlineKeyboardButton("Добавить в мои приложения", callback_data="add_to_my_apps_web")
    no_button = InlineKeyboardButton("Нет", callback_data="personal_cabinet")
    keyboard.row(add_app_button, no_button)

    await message.answer("Открыть ваш сайт:", reply_markup=keyboard)

    # Получаем идентификатор сообщения для удаления
    data = await state.get_data()
    message_to_delete_id = data.get('message_to_delete_id')

    # Удаляем сообщение с запросом ссылки
    if message_to_delete_id:
        await bot.delete_message(chat_id=message.chat.id, message_id=message_to_delete_id)

    # Проверяем, существует ли сообщение message и не было ли оно уже удалено
    if message:
        try:
            await message.delete()
        except aiogram.utils.exceptions.MessageToDeleteNotFound:
            pass

    # Проверяем, существует ли сообщение message и не было ли оно уже удалено
    if message:
        try:
            await message.delete()
        except aiogram.utils.exceptions.MessageToDeleteNotFound:
            pass

    # Проверяем, существует ли сообщение message и не было ли оно уже удалено
    if message:
        try:
            await message.delete()
        except aiogram.utils.exceptions.MessageToDeleteNotFound:
            pass


# Обработчик сообщений для добавления ссылок из обычного ввода
@dp.message_handler(state="websearch", content_types=types.ContentType.TEXT)
async def receive_link_web(message: types.Message, state: FSMContext):
    user_link = message.text
    if not user_link.startswith("http"):
        await message.delete()
        return
    domain_name = urlparse(user_link).netloc
    button_text = domain_name if domain_name else user_link
    button = InlineKeyboardButton(button_text, web_app=WebAppInfo(url=user_link))
    keyboard = InlineKeyboardMarkup().add(button)
    await state.update_data(url=user_link)
    add_app_button = InlineKeyboardButton("Добавить в мои приложения", callback_data="add_to_my_apps")
    no_button = InlineKeyboardButton("Нет", callback_data="back_kabinet")
    keyboard.row(add_app_button, no_button)
    await message.answer("Открыть ваш сайт:", reply_markup=keyboard)

    # Получаем идентификатор сообщения для удаления
    data = await state.get_data()
    message_to_delete_id = data.get('message_to_delete_id')

    # Удаляем сообщение с запросом ссылки
    if message_to_delete_id:
        await bot.delete_message(chat_id=message.chat.id, message_id=message_to_delete_id)

    # Проверяем, существует ли сообщение message и не было ли оно уже удалено
    if message:
        try:
            await message.delete()
        except aiogram.utils.exceptions.MessageToDeleteNotFound:
            pass


# Обработчик для кнопки "Мои приложения"
@dp.callback_query_handler(lambda query: query.data == "my_apps")
async def handle_my_apps_button(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    # Получаем список приложений пользователя
    apps_list = get_user_apps(user_id)
    if not apps_list:
        # Удаляем предыдущее сообщение пользователя
        await callback_query.message.delete()
        # Если у пользователя нет приложений, выводим сообщение и предлагаем добавить новое приложение или вернуться
        # в меню
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("Добавить приложение", callback_data="addwebsearch"),
            InlineKeyboardButton("Нет", callback_data="personal_cabinet")  # Добавляем кнопку "Нет"
        )
        message = "На данный момент у вас нет приложений. Хотите добавить новое приложение?"
        await callback_query.message.answer(message, reply_markup=keyboard)
        return

    # Создаем список кнопок для каждого приложения пользователя
    buttons = []
    for index, app_link in enumerate(apps_list):
        # Извлекаем доменное имя из URL
        domain_name = urlparse(app_link).netloc
        # Если доменное имя пустое, используем весь URL в качестве названия
        button_text = domain_name if domain_name else app_link
        # Создаем кнопку для каждого приложения с использованием WebAppInfo
        button = InlineKeyboardButton(button_text, web_app=WebAppInfo(url=app_link))
        buttons.append(button)

    buttons.append(InlineKeyboardButton("➕", callback_data="websearch")),
    buttons.append(InlineKeyboardButton("Удалить приложение", callback_data="delete_app"))
    # Добавляем кнопку "Назад"
    buttons.append(InlineKeyboardButton("Назад", callback_data="personal_cabinet"))

    # Создаем клавиатуру с кнопками для приложений пользователя
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(*buttons)

    # Удаляем предыдущее сообщение пользователя
    await callback_query.message.delete()

    # Отправляем новое сообщение с кнопками пользователю
    await callback_query.message.answer("Ваши приложения:", reply_markup=keyboard)


@dp.callback_query_handler(lambda query: query.data == "delete_app")
async def handle_delete_app_button(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    apps_list = get_user_apps(user_id)
    if not apps_list:
        await callback_query.answer("У вас нет приложений для удаления.")
        return

    # Создаем клавиатуру с кнопками для каждого приложения
    buttons = [InlineKeyboardButton(f"Удалить {urlparse(app).netloc or app}", callback_data=f"delete_{index}")
               for index, app in enumerate(apps_list)]

    # Добавляем кнопку "Назад"
    buttons.append(InlineKeyboardButton("Назад", callback_data="my_apps"))

    # Создаем клавиатуру для удаления приложений
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(*buttons)

    # Удаляем предыдущее сообщение пользователя
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)

    # Отправляем новое сообщение с кнопками для удаления приложений
    message = await callback_query.message.answer("Нажмите на приложение, которое хотите удалить:",
                                                  reply_markup=keyboard)

    # Сохраняем идентификатор сообщения, чтобы в дальнейшем обновлять его
    await dp.current_state(user=user_id).update_data(delete_message_id=message.message_id)


@dp.callback_query_handler(lambda query: query.data.startswith("delete_"))
async def delete_app_button(callback_query: types.CallbackQuery):
    try:
        app_index = int(callback_query.data.split("_")[1])  # Получаем индекс приложения из данных колбэка
        user_id = callback_query.from_user.id
        apps_list = get_user_apps(user_id)
        if 0 <= app_index < len(apps_list):
            # Если индекс находится в пределах списка, удаляем приложение по индексу
            deleted_app = apps_list.pop(app_index)
            # Удаляем приложение из базы данных
            delete_app_from_db(user_id, deleted_app)
            # Отправляем уведомление о том, что приложение удалено
            await callback_query.answer(f"Приложение '{deleted_app}' удалено из ваших приложений.")

            # Создаем клавиатуру с кнопками для оставшихся приложений
            buttons = [InlineKeyboardButton(f"Удалить {urlparse(app).netloc or app}", callback_data=f"delete_{index}")
                       for index, app in enumerate(apps_list)]
            # Добавляем кнопку "Назад"
            buttons.append(InlineKeyboardButton("Назад", callback_data="my_apps"))
            # Создаем клавиатуру для удаления приложений
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(*buttons)

            # Обновляем предыдущее сообщение пользователя
            await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                        message_id=callback_query.message.message_id,
                                        text="Нажмите на приложение, которое хотите удалить:",
                                        reply_markup=keyboard)
        else:
            await callback_query.answer("Ошибка: Неверный индекс приложения.")
    except Exception as e:
        await callback_query.answer("Произошла ошибка при удалении приложения.")
        print(e)


async def return_to_personal_cabinet(callback_query: types.CallbackQuery):
    # Создаем клавиатуру с кнопками для личного кабинета
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Личный кабинет", callback_data="personal_cabinet"))
    # Отправляем сообщение с кнопками для возвращения в личный кабинет
    await callback_query.message.answer("Вернуться в Личный кабинет:", reply_markup=keyboard)


# Обработчик возвращения в меню
@dp.callback_query_handler(text="back_kabinet", state="*")
async def back_kabinet(callback_query: types.CallbackQuery, state: FSMContext):
    # Удаляем предыдущее сообщение с запросом ключевого слова
    await callback_query.message.delete()
    await callback_query.answer()
    await state.finish()


# Обработчик возвращения в меню
@dp.callback_query_handler(text="back_so_kabinet", state="*")
async def back_so_kabinet(callback_query: types.CallbackQuery, state: FSMContext):
    # Удаляем предыдущее сообщение с запросом ключевого слова
    await callback_query.message.delete()
    await callback_query.answer()
    await start(callback_query.message, state)

@dp.callback_query_handler(text="back_so_vk", state="*")
async def back_so_vk(callback_query: types.CallbackQuery, state: FSMContext):
    # Удаляем предыдущее сообщение с запросом ключевого слова
    await callback_query.message.delete()


# Обработчик возвращения в меню
@dp.callback_query_handler(text="back_to_menu", state="*")
async def back_to_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await start(callback_query.message, state)


# ____________________________________________VK_______________________________________________________________________________________________________
async def send_vk_posts_file(message: types.Message, filename: str):
    with open(filename, 'rb') as file:
        await message.answer_document(file)

def search_vk_content(keyword, offset=0, count=100):
    try:
        max_posts = 500
        posts = []
        total_posts = 0
        while total_posts < max_posts:
            search_url = f"https://api.vk.com/method/newsfeed.search?q={keyword}&count={count}&offset={offset}&filters=wall,post,video,photo,audio,doc,note,poll,page,link,market&access_token={VK_ACCESS_TOKEN}&v=5.131"
            response = requests.get(search_url).json()
            items = response.get('response', {}).get('items', [])
            if not items:
                break
            posts.extend(items)
            total_posts += len(items)
            offset += count
        return posts[:max_posts]  # Return up to 1000 posts
    except Exception as e:
        logger.error(f"Error searching VK content: {e}")
        return []

@dp.callback_query_handler(lambda query: query.data == "vk_search_type", state="*")
async def search_vk_type_callback(query: types.CallbackQuery, state: FSMContext):
    await Form.vk_search_type.set()
    keyboard_markup = InlineKeyboardMarkup()
    keyboard_markup.row(
        InlineKeyboardButton("Обычный поиск 🔎", callback_data="vk_search"),
        InlineKeyboardButton("Парсинг постов 📋", callback_data="vk_parse"),
    )
    keyboard_markup.row(
        InlineKeyboardButton("Назад ↩️", callback_data="back_so_vk")
    )
    await query.message.answer("Выберите тип поиска:", reply_markup=keyboard_markup)
    await query.answer(text="", show_alert=True)


@dp.callback_query_handler(lambda query: query.data == "vk_search", state="*")
async def search_vk_callback(query: types.CallbackQuery, state: FSMContext):
    await Form.vk_search.set()
    user_id = query.from_user.id
    if update_request_limit(user_id):
        await Form.vk_search.set()
        message = await query.message.answer("Введите ключевое слово для обычного поиска в VK 🕵️‍♂️:")

        await state.update_data(source="vk")
        await state.update_data(previous_message_id=message.message_id)
        await query.answer(text="", show_alert=True)
        user_id = query.from_user.id
    else:
        await query.answer("У вас закончились доступные запросы на сегодня.")


@dp.callback_query_handler(lambda query: query.data == "vk_parse", state="*")
async def vk_parse_callback(query: types.CallbackQuery, state: FSMContext):
    await Form.vk_parse.set()
    user_id = query.from_user.id
    if update_request_limit(user_id):
        await Form.vk_parse.set()
        message = await query.message.answer("Введите ключевое слово для парсинга в VK 🕵️‍♂️:")

        await state.update_data(source="vk")
        await state.update_data(previous_message_id=message.message_id)
        await query.answer(text="", show_alert=True)
        user_id = query.from_user.id
    else:
        await query.answer("У вас закончились доступные запросы на сегодня.")


@dp.message_handler(state=Form.vk_parse)
async def vk_parse_execute(message: types.Message, state: FSMContext):
    keyword = message.text

    await message.delete()

    # Формируем сообщение с ключевым словом
    search_message = f"Выполняется загрузка 500 постов на ключевое слово \"{keyword}\""
    await message.answer(search_message)

    # Инициализируем keyword и offset в контексте состояния
    await state.update_data(keyword=keyword, offset=0)

    posts = search_vk_content(keyword)
    if posts:
        filename = await send_vk_posts_to_excel(keyword, posts)
        await send_vk_posts_file(message, filename)  # Отправляем файл с постами
    else:
        await message.answer("По вашему запросу ничего не найдено 😔.")
        await state.finish()

async def send_vk_posts_to_excel(keyword: str, posts: list):
    wb = openpyxl.Workbook()
    ws = wb.active

    # Записываем заголовки
    headers = ["Номер поста", "Текст поста", "Количество лайков", "Количество комментариев", "Количество просмотров",
               "Дата выложенного поста", "Ссылка на пост"]
    ws.append(headers)

    # Записываем данные по постам
    for post in posts:
        post_text = post.get('text', '')
        if len(post_text) > 100:
            post_text = f"{post_text[:100]}..."
        post_link = f"https://vk.com/wall{post['owner_id']}_{post['id']}"
        likes_count = format_number(post['likes']['count'])
        comments_count = format_number(post['comments']['count'])
        views_count = format_number(post.get('views', {}).get('count', '0'))
        post_date = datetime.fromtimestamp(post['date']).strftime('%Y-%m-%d %H:%M:%S')

        row_data = [post['id'], post_text, likes_count, comments_count, views_count, post_date, post_link]
        ws.append(row_data)

    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        filename = tmp_file.name
        wb.save(filename)

    return filename

@dp.message_handler(state=Form.vk_search)
async def vk_search_execute(message: types.Message, state: FSMContext):
    # Получаем тип сортировки из состояния
    sent_posts.clear()
    data = await state.get_data()
    sort_type = data.get('sort_type')

    keyword = message.text

    await message.delete()

    # Формируем сообщение с ключевым словом
    search_message = f"Посты на ключевое слово \"{keyword}\""
    await message.answer(search_message)

    # Инициализируем keyword и offset в контексте состояния
    await state.update_data(keyword=keyword, offset=0)

    # Выполняем поиск постов
    posts = search_vk_content(keyword)
    if posts:
        # Сортируем посты в соответствии с выбранной сортировкой
        if sort_type == "date_desc":
            posts.sort(key=lambda x: x['likes']['count'] + x['comments']['count'], reverse=True)
        await send_vk_posts(message, state, keyword, posts, 0)
    else:
        await message.answer("По вашему запросу ничего не найдено 😔.")
        await state.finish()


@dp.callback_query_handler(lambda query: query.data == "show_more_posts", state=MyStates.sending_links)
async def show_more_posts(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    keyword = data.get('keyword')
    offset = data.get('offset', 0) + 5  # Увеличиваем offset на 5

    # Отправляем номер списка постов
    await callback_query.message.answer(f"Список постов №{(offset // 5) + 1}")

    posts = search_vk_content(keyword, offset)
    if posts:
        await send_vk_posts(callback_query.message, state, keyword, posts, offset)
        await state.update_data(offset=offset)  # Обновляем offset в контексте состояния
    else:
        await callback_query.answer("Больше результатов нет.")
    await callback_query.answer()

    reply_message_id = data.get('reply_message_id')
    if reply_message_id:
        await bot.delete_message(callback_query.message.chat.id, reply_message_id)


@dp.callback_query_handler(lambda query: query.data == "no_show_more_posts", state=MyStates.sending_links)
async def no_show_more_posts(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Окей, возвращаю вас на главное меню.")
    await start(callback_query.message, state)
    await MyStates.waiting_for_keyword.set()
    await callback_query.answer(text="", show_alert=True)

    # Удаляем сообщение с кнопками
    data = await state.get_data()
    reply_message_id = data.get('reply_message_id')
    if reply_message_id:
        await bot.delete_message(callback_query.message.chat.id, reply_message_id)
    await callback_query.message.delete()


async def unique_pages(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_and_hash(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
    unique_content = {}
    for url, content_hash in results:
        if content_hash and content_hash not in unique_content:
            unique_content[content_hash] = url
    return list(unique_content.values())


async def fetch_and_hash(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                content = await response.text()
                content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                return url, content_hash
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
    return url, None


def canonicalize_url(url):
    parsed_url = urlparse(url)
    parsed_query = parse_qs(parsed_url.query, keep_blank_values=True)
    query = parsed_url.query
    # Можно добавить логику для канонизации query-параметров
    canonical_url = urlunparse(parsed_url._replace(query=query))
    return canonical_url


async def send_vk_posts(message: types.Message, state: FSMContext, keyword: str, posts: list, offset: int):
    if not posts:
        await message.answer("По вашему запросу ничего не найдено.")
        return

    # Получаем текущий счётчик отправленных постов
    data = await state.get_data()
    sent_count = data.get('sent_count', 0)

    for post in posts[sent_count:sent_count + 5]:
        if post['id'] not in sent_posts:
            post_text = post.get('text', '')
            if len(post_text) > 100:
                post_text = f"{post_text[:100]}..."
            post_link = f"https://vk.com/wall{post['owner_id']}_{post['id']}"
            likes_count = format_number(post['likes']['count'])
            comments_count = format_number(post['comments']['count'])
            views_count = format_number(post.get('views', {}).get('count', '0'))
            message_text = f"{post_text}\nСсылка на пост: {post_link}\n❤️ {likes_count}\n✉️ {comments_count}\n👀 {views_count}"

            if 'attachments' in post:
                for attachment in post['attachments']:
                    if attachment['type'] == 'video':
                        video = attachment['video']
                        video_link = f"https://vk.com/video{video['owner_id']}_{video['id']}"
                        message_text += f"\n📹 Видео: {video_link}"

            await message.answer(message_text)
            sent_posts.add(post['id'])
            sent_count += 1

    await state.update_data(sent_count=sent_count)

    if sent_count < len(posts):
        keyboard_markup = InlineKeyboardMarkup()
        keyboard_markup.row(
            InlineKeyboardButton("Да", callback_data="show_more_posts"),
            InlineKeyboardButton("Нет", callback_data="no_show_more_posts")
        )
        reply_message = await message.answer("Показать еще посты?", reply_markup=keyboard_markup)
        await MyStates.sending_links.set()

        await state.update_data(reply_message_id=reply_message.message_id)
    else:
        await message.answer("Больше результатов нет.")
        await state.finish()



# ____________________________________________Telegram_________________________________________________________________________________________________
client = None

async def connect_telegram_client():
    global client
    if client is None or not client.is_connected():
        client = TelegramClient(session_file_name, api_id, api_hash)
        await client.start()
        if not client.is_user_authorized():
            await client.send_code_request('phone_number')
            await client.sign_in('phone_number', input('Enter code: '))

@dp.callback_query_handler(lambda query: query.data == "telegram_publics", state="*")
async def search_telegram_publics_callback(query: types.CallbackQuery, state: FSMContext):
    user_id = query.from_user.id

    remaining_requests = get_remaining_requests(user_id)
    if remaining_requests == 0:
        await query.answer("У вас закончились доступные запросы на сегодня.")
        return

    if update_request_limit(user_id):
        message = await query.message.answer("Введите ключевое слово для поиска в Телеграмм Пабликах 📢:")
        await MyStates.waiting_for_telegram_publics_keyword.set()
        await state.update_data(previous_message_id=message.message_id)
        await query.answer(text="", show_alert=True)
    else:
        await query.answer("У вас закончились доступные запросы на сегодня.")

async def send_posts(chat_id, posts, offset, state):
    for post in posts:
        truncated_text = post['text'][:200] + '...' if len(post['text']) > 200 else post['text']
        await bot.send_message(chat_id, f"{truncated_text}\nСсылка на пост: {post['link']}")
    await state.update_data(offset=offset + 10)

async def search_telegram_publics(inner_client, keyword, message, state: FSMContext):
    found_posts = []
    try:
        data = await state.get_data()
        previous_message_id = data.get('previous_message_id')
        if previous_message_id:
            await bot.delete_message(message.chat.id, previous_message_id)
        await bot.delete_message(message.chat.id, message.message_id)

        await message.answer(f"Поиск начат по \"{keyword}\". Пожалуйста, подождите примерно 15-25 секунд.")

        dialogs = await inner_client.get_dialogs()

        async def search_dialog(dialog):
            nonlocal found_posts
            if isinstance(dialog.entity, Channel) and dialog.entity.username:
                try:
                    async for msg in inner_client.iter_messages(dialog.entity, search=keyword, limit=200):
                        if keyword.lower() in msg.text.lower():
                            post_link = f"https://t.me/{dialog.entity.username}/{msg.id}"
                            found_posts.append({
                                'text': msg.text,
                                'link': post_link,
                                'date': msg.date
                            })
                            if len(found_posts) >= 200:
                                break
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds + 5)

        tasks = [search_dialog(dialog) for dialog in dialogs]
        await asyncio.gather(*tasks)
    except AuthKeyUnregisteredError:
        await inner_client.start()
    except ConnectionError:
        raise

    found_posts.sort(key=lambda x: x['date'], reverse=True)
    return found_posts

@dp.message_handler(state=MyStates.waiting_for_telegram_publics_keyword)
async def process_keyword_telegram_publics(message: types.Message, state: FSMContext):
    keyword = message.text
    try:
        async with TelegramClient('anon', api_id, api_hash) as inner_client:
            posts = await search_telegram_publics(inner_client, keyword, message, state)
            if posts:
                await state.update_data(found_posts=posts, keyword=keyword)
                await send_posts(message.chat.id, posts[:10], 0, state)
                if len(posts) > 10:
                    await message.answer("Хотите увидеть еще посты?", reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton("Да", callback_data="show_more_posts"),
                        InlineKeyboardButton("Нет", callback_data="no_show_more_posts")
                    ))
                await state.update_data(previous_message_id=message.message_id)
                try:
                    data = await state.get_data()
                    previous_message_id = data.get('previous_message_id')
                    if previous_message_id:
                        await bot.delete_message(message.chat.id, previous_message_id)
                    await bot.delete_message(message.chat.id, message.message_id)
                except aiogram.utils.exceptions.MessageToDeleteNotFound:
                    pass
            else:
                await message.answer("По вашему запросу ничего не найдено 😔.")
    except ConnectionError:
        await message.answer("Произошла ошибка при соединении с сервером Telegram. Пожалуйста, попробуйте снова позже.")

@dp.callback_query_handler(lambda query: query.data == "show_more_posts", state="*")
async def show_more_posts_callback(query: types.CallbackQuery, state: FSMContext):
    await query.message.answer("Следующие посты")
    await bot.delete_message(query.message.chat.id, query.message.message_id)
    data = await state.get_data()
    offset = data.get("offset", 0)
    keyword = data.get("keyword")
    found_posts = data.get("found_posts", [])
    try:
        if found_posts:
            await send_posts(query.message.chat.id, found_posts[offset:offset + 10], offset, state)
            if len(found_posts) > offset + 10:
                await query.message.answer("Хотите увидеть еще посты?", reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("Да", callback_data="show_more_posts"),
                    InlineKeyboardButton("Нет", callback_data="no_show_more_posts")
                ))
            else:
                await query.message.answer("Поиск завершен.")
        else:
            async with TelegramClient('anon', api_id, api_hash) as inner_client:
                posts = await search_telegram_publics(inner_client, keyword, query.message, state)
                if posts:
                    await send_posts(query.message.chat.id, posts[offset:offset + 10], offset, state)
                    if len(posts) > offset + 10:
                        await query.message.answer("Хотите увидеть еще посты?", reply_markup=InlineKeyboardMarkup().add(
                            InlineKeyboardButton("Да", callback_data="show_more_posts"),
                            InlineKeyboardButton("Нет", callback_data="no_show_more_posts")
                        ))
                    else:
                        await query.message.answer("Поиск завершен.")
                else:
                    await query.message.answer("По вашему запросу больше нет постов.")
    except ConnectionError:
        await query.message.answer("Произошла ошибка при соединении с сервером Telegram.")

@dp.callback_query_handler(lambda query: query.data == "no_show_more_posts", state="*")
async def no_show_more_posts_callback(query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    previous_message_id = data.get('previous_message_id')

    try:
        if previous_message_id:
            await bot.delete_message(query.message.chat.id, previous_message_id)
    except aiogram.utils.exceptions.MessageToDeleteNotFound:
        pass

    await bot.delete_message(query.message.chat.id, query.message.message_id)
    await show_menu(query.message)


# ____________________________________________youtube_________________________________________________________________________________________________
async def search_youtube(query, page_token=None):
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': query,
        'key': YOUTUBE_API_KEY,
        'maxResults': 5,
        'type': 'video'
    }
    # Добавляем pageToken в параметры только если он не None
    if page_token is not None:
        params['pageToken'] = page_token

    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data['items'], data.get('nextPageToken')  # Возвращаем результаты и токен следующей страницы
            else:
                print("Failed to fetch YouTube data")
                return [], None


@dp.callback_query_handler(lambda query: query.data == "youtube", state="*")
async def prompt_youtube_search(query: types.CallbackQuery, state: FSMContext):
    user_id = query.from_user.id

    # Проверяем количество оставшихся запросов
    remaining_requests = get_remaining_requests(user_id)
    if remaining_requests == 0:
        await query.answer("У вас закончились доступные запросы на сегодня.")
        return

    # Уменьшаем лимит запросов пользователя, если у него остались запросы
    if update_request_limit(user_id):
        # Если оставшиеся запросы есть, продолжаем выполнение действия
        await MyStates.waiting_for_youtube_search.set()
        message = await query.message.answer("Введите свой поисковый запрос для поиска видео на YouTube:")

        await state.update_data(source="youtube")  # Сохраняем источник поиска в состоянии
        await state.update_data(previous_message_id=message.message_id)  # Сохраняем ID предыдущего сообщения
        await query.answer(text="", show_alert=True)  # Убираем свечение кнопок
    else:
        await query.answer("У вас закончились доступные запросы на сегодня.")


async def get_youtube_video_statistics(video_id):
    statistics_url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        'part': 'statistics',
        'id': video_id,
        'key': YOUTUBE_API_KEY
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(statistics_url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                # Возвращаем статистику видео (лайки, комментарии, просмотры)
                return data['items'][0]['statistics']
            else:
                print("Failed to fetch video statistics")
                return {}


@dp.message_handler(state=MyStates.waiting_for_youtube_search)
async def perform_youtube_search(message: types.Message, state: FSMContext):
    query = message.text

    # Получаем ID предыдущего сообщения пользователя
    data = await state.get_data()
    previous_message_id = data.get('previous_message_id')

    # Удаляем предыдущее сообщение пользователя
    if previous_message_id:
        await message.bot.delete_message(message.chat.id, previous_message_id)

    # Удаляем также сообщение с запросом ключевого слова
    await message.delete()

    # Формируем сообщение с ключевым словом
    search_message = f"Поиск видео по ключевому слову \"{query}\""
    await message.answer(search_message)

    videos, next_page_token = await search_youtube(query)

    if not videos:
        await message.answer("По вашему запросу не найдено видео.")
        await state.finish()
    else:
        for video in videos:
            video_id = video['id']['videoId']
            title = video['snippet']['title']
            response_message = f"📹 [{title}](https://www.youtube.com/watch?v={video_id})\n"
            statistics = await get_youtube_video_statistics(video_id)
            likes = int(statistics.get('likeCount', 0))
            comments = int(statistics.get('commentCount', 0))
            views = int(statistics.get('viewCount', 0))

            # Форматирование чисел в зависимости от их значения
            likes_str = format_number(likes)
            comments_str = format_number(comments)
            views_str = format_number(views)

            response_message += f"Лайки ❤️: {likes_str}\nКомментарии ✉️: {comments_str}\nПросмотры 👀: {views_str}"
            await message.answer(response_message, parse_mode="Markdown")

        if next_page_token:
            # Обновляем состояние для ожидания следующей страницы результатов
            await MyStates.waiting_for_next_page.set()
            await state.update_data(query=query, next_page_token=next_page_token)

            # Добавляем кнопки для показа еще результатов
            markup = InlineKeyboardMarkup(row_width=2).add(
                InlineKeyboardButton("Да", callback_data="show_more_youtube"),
                InlineKeyboardButton("Нет", callback_data="no_show_more_youtube")
            )
            await message.answer("Показать еще результаты?", reply_markup=markup)


def format_number(number):
    if isinstance(number, int):  # Проверяем, является ли число целым числом
        if number < 10000:
            return str(number)
        elif number < 1000000:
            return f"{number // 1000} тыс."
        elif number < 1000000000:
            return f"{number // 1000000} млн."
        else:
            return f"{number // 1000000000} млд."
    else:
        return str(number)  # Возвращаем исходную строку, если значение не является числом



@dp.callback_query_handler(text="no_show_more_youtube", state=MyStates.waiting_for_next_page)
async def no_more_youtube(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    # Сообщение пользователю, что он возвращается в главное меню
    await callback_query.message.answer("Возвращаем вас в главное меню.")
    # Сбрасываем текущее состояние
    await state.reset_state()
    # Вызов функции, которая инициирует главное меню
    await start(callback_query.message, state)

@dp.callback_query_handler(text="show_more_youtube", state=MyStates.waiting_for_next_page)
async def show_more_youtube(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    query = user_data['query']
    next_page_token = user_data['next_page_token']
    offset = user_data.get('offset', 0) + 5  # Увеличиваем offset на 5

    # Определяем текущий номер страницы
    page_number = (offset // 5) + 1

    # Fetch the next set of videos using the YouTube API
    videos, next_page_token = await search_youtube(query, next_page_token)

    if not videos:
        # If there are no more videos, inform the user and reset the state
        await callback_query.message.answer("Больше видео нет.")
        await state.reset_state()
        return

    # Send each video as a separate message
    for i, video in enumerate(videos, start=offset + 1):
        video_id = video['id']['videoId']
        title = video['snippet']['title']
        response_message = f"Список видео №{page_number}, видео {i}: [{title}](https://www.youtube.com/watch?v={video_id})\n"
        statistics = await get_youtube_video_statistics(video_id)
        likes = int(statistics.get('likeCount', 0))
        comments = int(statistics.get('commentCount', 0))
        views = int(statistics.get('viewCount', 0))

        # Форматирование чисел в зависимости от их значения
        likes_str = format_number(likes)
        comments_str = format_number(comments)
        views_str = format_number(views)

        response_message += f"Лайки ❤️: {likes_str}\nКомментарии ✉️: {comments_str}\nПросмотры 👀: {views_str}"
        await callback_query.message.answer(response_message, parse_mode="Markdown")

    # If there is a token for more pages, provide the option to fetch more videos
    if next_page_token:
        # Delete the original message with the "Show more" button
        await callback_query.message.delete()
        # Update the inline keyboard to include "Yes" and "No" options for fetching more videos
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Да", callback_data="show_more_youtube"),
            InlineKeyboardButton("Нет", callback_data="no_show_more_youtube")
        )
        await callback_query.message.answer("Показать еще результаты?", reply_markup=markup)
        await state.update_data(query=query, next_page_token=next_page_token, offset=offset)
    else:
        # If there are no more pages, inform the user and reset the state
        await callback_query.message.answer("Больше видео нет.")
        await state.reset_state()

# ____________________________________________instagram_________________________________________________________________________________________________

@dp.callback_query_handler(lambda query: query.data == "instagram", state="*")
async def instagram_search_callback(query: types.CallbackQuery, state: FSMContext):
    user_id = query.from_user.id

    # Проверяем количество оставшихся запросов
    remaining_requests = get_remaining_requests(user_id)
    if remaining_requests == 0:
        await query.answer("У вас закончились доступные запросы на сегодня.")
        return

    # Уменьшаем лимит запросов пользователя, если у него остались запросы
    if update_request_limit(user_id):
        # Если оставшиеся запросы есть, продолжаем выполнение действия
        message = await query.message.answer("Бета тест\nВведите ключевое слово для поиска в Instagram:")
        await Form.instagram_search.set()  # Устанавливаем состояние ожидания поискового запроса в Instagram
        await state.update_data(source="instagram")  # Сохраняем источник поиска в состоянии
        await state.update_data(previous_message_id=message.message_id)  # Сохраняем ID предыдущего сообщения
        await query.answer(text="", show_alert=True)  # Убираем свечение кнопок
    else:
        await query.answer("У вас закончились доступные запросы на сегодня.")


async def search_instagram_posts(keyword, page=0):
    formatted_keyword = quote_plus(keyword)
    all_instagram_links = []
    while page < 50:  # Увеличиваем количество страниц, которые хотим проверить
        google_search_url = (
            f"https://www.google.com/search?q=site:instagram.com/p/+{formatted_keyword}"
            f"&start={page * 50}"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}

        async with aiohttp.ClientSession() as session:
            async with session.get(google_search_url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    links = soup.find_all('a', href=True)
                    instagram_links = []

                    for link in links:
                        href = link['href']
                        # Проверяем наличие нужной ссылки в href
                        if 'https://www.instagram.com/p/' in href:
                            # Ищем нужный участок в ссылке
                            match = re.search(r'/url\?q=(https://www\.instagram\.com/p/[^&]+)', href)
                            if match:
                                clean_url = match.group(1)
                                instagram_links.append(clean_url)

                    all_instagram_links.extend(instagram_links)

                    next_page = soup.select_one(
                        'a#pnnext'  # Используем подходящий селектор для кнопки "Следующая страница"
                    )
                    if next_page:
                        page += 1
                    else:
                        break
    return list(set(all_instagram_links)), False


# Обработчик поиска в Instagram
@dp.message_handler(state=Form.instagram_search)
async def instagram_search_execute(message: types.Message, state: FSMContext):
    keyword = message.text
    page = 0  # Страница результатов Google
    all_posts = []

    # Получаем ID предыдущего сообщения пользователя
    data = await state.get_data()
    previous_message_id = data.get('previous_message_id')

    # Удаляем предыдущее сообщение пользователя
    if previous_message_id:
        await message.bot.delete_message(message.chat.id, previous_message_id)

    # Удаляем также сообщение с запросом ключевого слова
    await message.delete()

    # Формируем сообщение с ключевым словом
    search_message = f"Поиск инстаграму по ключевому слову \"{keyword}\""
    await message.answer(search_message)

    # Получаем результаты с первой страницы
    posts, has_next_page = await search_instagram_posts(keyword, page)
    all_posts.extend(posts)

    # Продолжаем запрашивать следующие страницы, если есть
    while has_next_page and len(all_posts) < 50:  # Ограничиваем общее количество результатов, например, до 50
        page += 1
        posts, has_next_page = await search_instagram_posts(keyword, page)
        all_posts.extend(posts)

    # Обновляем состояние с полученными результатами
    if all_posts:
        await state.update_data(posts=all_posts, position=0)
        await InstagramPagination.showing_results.set()
        await show_results(message, state)
    else:
        await message.answer("По вашему запросу в Instagram не найдено результатов.")
        await state.finish()


# Функция для показа результатов
async def show_results(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    posts = user_data['posts']
    position = user_data['position']
    # Показываем до 5 результатов за раз
    for index in range(position, min(position + 5, len(posts))):
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Перейти на пост", url=posts[index])
        )
        await message.answer(f"Пост {index + 1}", reply_markup=markup)

    # Если есть еще посты для показа
    if position + 5 < len(posts):
        await InstagramPagination.confirm_continuation.set()
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Да", callback_data="yes_more"),
            InlineKeyboardButton("Нет", callback_data="no_more")
        )
        await message.answer("Показать еще?", reply_markup=markup)
    else:
        # Сообщаем пользователю, что постов больше нет, и предлагаем вернуться в меню
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Вернуться в меню", callback_data="back_to_menu")
        )
        await message.answer("Больше постов нет.", reply_markup=markup)
        await state.finish()


# Обработчик подтверждения пользователя на показ еще результатов
@dp.callback_query_handler(text="yes_more", state=InstagramPagination.confirm_continuation)
async def confirm_yes_more(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    user_data = await state.get_data()
    position = user_data['position'] + 5
    await state.update_data(position=position)
    await InstagramPagination.showing_results.set()
    await show_results(callback_query.message, state)


@dp.callback_query_handler(text="no_more", state=InstagramPagination.confirm_continuation)
async def confirm_no_more(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    await callback_query.answer("Возвращаем вас в главное меню.")
    await state.finish()
    await start(callback_query.message, state)


# ____________________________________________google_search_________________________________________________________________________________________________


@dp.callback_query_handler(lambda query: query.data == "google_search", state="*")
async def google_search_callback(query: types.CallbackQuery, state: FSMContext):
    user_id = query.from_user.id

    # Проверяем количество оставшихся запросов
    remaining_requests = get_remaining_requests(user_id)
    if remaining_requests == 0:
        await query.answer("У вас закончились доступные запросы на сегодня.")
        return

    # Уменьшаем лимит запросов пользователя, если у него остались запросы
    if update_request_limit(user_id):
        update_request_limit(user_id)
        # Если оставшиеся запросы есть, продолжаем выполнение действия
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Обычный 🌐", callback_data="google_normal_search"),
            InlineKeyboardButton("Фотографии 🖼️", callback_data="google_image_search"),
            InlineKeyboardButton("Назад ↩️", callback_data="back_so_vk")
        )
        await query.message.answer("Выберите тип поиска:", reply_markup=markup)
        await SearchType.choosing_google_search_type.set()
        await query.answer(text="", show_alert=True)  # Убираем свечение кнопок
    else:
        await query.answer("У вас закончились доступные запросы на сегодня.")



@dp.callback_query_handler(lambda query: query.data == "google_normal_search",
                           state=SearchType.choosing_google_search_type)
async def set_google_normal_search(query: types.CallbackQuery, state: FSMContext):
    # Удаляем сообщение с выбором типа поиска
    await query.message.delete()

    # Сохраняем ID предыдущего сообщения
    previous_message_id = query.message.message_id
    await state.update_data(google_search_type="normal", previous_message_id=previous_message_id)

    # Отправляем сообщение для ввода поискового запроса
    message = await query.message.answer("Введите свой поисковый запрос для поиска сайтов в google:")

    # Устанавливаем тип поиска в состояние и переходим к следующему шагу
    await state.update_data(source="google_normal_search", input_message_id=message.message_id)
    await MyStates.waiting_for_google_search_keyword.set()


@dp.callback_query_handler(lambda query: query.data == "google_image_search",
                           state=SearchType.choosing_google_search_type)
async def set_google_image_search(query: types.CallbackQuery, state: FSMContext):
    # Аналогично удаляем сообщение с выбором типа поиска
    await query.message.delete()

    # Сохраняем ID предыдущего сообщения
    previous_message_id = query.message.message_id
    await state.update_data(google_search_type="images", previous_message_id=previous_message_id)

    # Отправляем сообщение для ввода поискового запроса
    message = await query.message.answer("Введите свой поисковый запрос для поиска фотографий в google:")

    # Устанавливаем тип поиска в состояние и переходим к следующему шагу
    await state.update_data(source="google_image_search", input_message_id=message.message_id)
    await MyStates.waiting_for_google_search_keyword.set()


api_keys = [
    {"key": "AIzaSyBdwmhpxjdGX8VWKaLvPB309sm0JktCK7U", "is_limit_reached": False},
    {"key": "AIzaSyA4m7Ms0PIozHHc5CuBsi6T0Y-pqK0gKsw", "is_limit_reached": False},
    {"key": "AIzaSyBVMuHW3rRuSA-nHukGZ11H5IoVtB0z1tI", "is_limit_reached": False}
]

current_api_key_index = 0  # Начнем с первого ключа в списке


async def google_search(query: str, cse_id: str, start_index=1, search_type=None):
    global current_api_key_index
    while current_api_key_index < len(api_keys):
        api_key = api_keys[current_api_key_index]["key"]
        search_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': cse_id,
            'q': query,
            'start': start_index
        }

        if search_type == "images":
            params['searchType'] = 'image'
            params['num'] = 10  # Максимум 10 изображений за запрос

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('items', [])
                    next_index = data.get('queries', {}).get('nextPage', [{}])[0].get('startIndex', None)
                    return items, next_index
                elif response.status in (403, 429):  # Handling both rate limit and quota exceeded errors
                    logging.warning(
                        f"API key limit reached or too many requests: HTTP {response.status}. Switching key...")
                    api_keys[current_api_key_index]["is_limit_reached"] = True
                    current_api_key_index = (current_api_key_index + 1) % len(
                        api_keys)  # Rotate to next key or start over
                    if all(key['is_limit_reached'] for key in api_keys):
                        logging.error("All API keys have reached their limit.")
                        return [], None
                else:
                    logging.error(f"Google search error: HTTP {response.status}")
                    return [], None
    logging.error("No valid API keys available.")
    return [], None


# Add this import
@dp.message_handler(state=MyStates.waiting_for_google_search_keyword)
async def google_search_execute(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    keyword = message.text
    google_search_type = user_data.get("google_search_type", "normal")

    # Получаем ID предыдущего сообщения пользователя
    data = await state.get_data()
    previous_message_id = data.get('previous_message_id')

    try:
        # Удаляем предыдущее сообщение пользователя
        if previous_message_id:
            await message.bot.delete_message(message.chat.id, previous_message_id)
    except MessageToDeleteNotFound:
        pass  # Если сообщение для удаления не найдено, продолжаем выполнение без генерации ошибки

    # Удаляем сообщение для ввода поискового запроса
    input_message_id = user_data.get("input_message_id")
    if input_message_id:
        await message.bot.delete_message(message.chat.id, input_message_id)

    # Формируем сообщение с ключевым словом
    search_message = f"Поиск google по ключевому слову \"{keyword}\""
    await message.answer(search_message)

    # Отправляем сообщение о начале загрузки
    loading_message = await message.answer("Идет загрузка результатов...")

    # Удаляем сообщение с ключевым словом
    await message.delete()

    # Обновляем состояние с сохраненным ключевым словом
    await state.update_data(keyword=keyword)

    # Вызываем функцию google_search с указанием типа поиска
    results, next_index = await google_search(keyword, YOUR_CSE_ID, search_type=google_search_type)

    if not results:
        await loading_message.edit_text("По вашему запросу ничего не найдено.")
        await asyncio.sleep(0.5)  # Даем пользователю время на прочтение сообщения
        await show_menu(message)  # Показываем главное меню
        await loading_message.delete()  # Удаляем сообщение о загрузке
        await state.finish()
        return

    if google_search_type == "images":
        image_urls = [item['link'] for item in results]
        valid_images = await prepare_images(image_urls)
        if valid_images:
            await bot.send_media_group(message.chat.id, media=valid_images)
        else:
            await message.answer("Не удалось загрузить изображения.")
    else:
        response_message = "\n".join([f"{item['title']}\n{item['link']}" for item in results])
        await message.answer(response_message, disable_web_page_preview=True)

    # Удаление сообщения о загрузке после отправки результатов
    await loading_message.delete()

    # Проверяем, есть ли еще результаты для показа
    if next_index:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Да", callback_data="get_more_google"),
            InlineKeyboardButton("Нет", callback_data="no_more_google")
        )
        await message.answer("Показать еще результаты?", reply_markup=markup)
        await state.update_data(next_index=next_index)
    else:
        await message.answer("Больше результатов нет.")
        await show_menu(message)  # Показываем главное меню
        await state.finish()


def clean_url(url):
    # Разбираем URL и очищаем его от параметров
    parsed = urlparse(url)
    # Создаем чистый URL без параметров запроса
    clean_parsed = parsed._replace(query="")
    return urlunparse(clean_parsed)


MAX_IMAGE_SIZE = 25 * 5000 * 5000  # Максимальный размер изображения (10 МБ)


async def download_and_convert_image(session, url, attempt=1, max_attempts=1):
    try:
        timeout = ClientTimeout(total=5)  # Устанавливаем таймаут подключения и чтения в 5 секунд
        async with session.get(url, timeout=timeout) as response:
            if response.status == 200:
                image_data = await response.read()
                image = Image.open(io.BytesIO(image_data))
                image_converted = image.convert('RGB')
                buffer = io.BytesIO()
                image_converted.save(buffer, format='PNG')
                buffer.seek(0)
                # Проверяем размер изображения перед отправкой
                if len(buffer.getvalue()) > MAX_IMAGE_SIZE:
                    logging.warning(f"Image size too large: {len(buffer.getvalue())} bytes")
                    return None
                return types.InputMediaPhoto(media=types.InputFile(buffer, filename="image.png"))
            else:
                raise Exception(f"HTTP error {response.status}")
    except Exception as e:
        logging.error(f"Error loading image from {url}: {e}")
        if attempt < max_attempts:
            logging.info(f"Retrying... Attempt {attempt + 1} of {max_attempts}")
            return await download_and_convert_image(session, url, attempt + 1, max_attempts)
        else:
            return None


async def prepare_images(urls):
    async with ClientSession() as session:
        tasks = [download_and_convert_image(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        return [result for result in results if result is not None]


async def send_image_or_convert(message, url):
    # Split the URL to get the file extension
    file_extension = url.split('.')[-1].split('?')[0].lower()
    if file_extension in ['png', 'jpeg', 'gif', 'jpg']:
        try:
            # If the image is already in a supported format, try to send it directly
            await message.answer_photo(photo=url)
        except Exception as e:
            logging.error(f"Error sending image: {e}. Sending as a link instead.")
            await message.answer(url)
    else:
        # If the format is not supported, try to convert and send as PNG
        logging.info(f"Unsupported image format for {url}. Attempting to convert to PNG.")
        async with ClientSession() as session:
            image_buffer = await download_and_convert_image(session, url)
            if image_buffer:
                await message.answer_photo(photo=image_buffer)
            else:
                await message.answer("Failed to load image.")


async def prepare_image(session, url):
    try:
        # Пытаемся скачать и конвертировать любое изображение в PNG
        return await download_and_convert_image(session, url)
    except Exception as e:
        print(f"Ошибка при обработке изображения: {e}")
        return None


@dp.callback_query_handler(lambda query: query.data == "get_more_google",
                           state=MyStates.waiting_for_google_search_keyword)
async def get_more_google(callback_query: types.CallbackQuery, state: FSMContext):
    # Удаление предыдущего сообщения с кнопками
    message_to_delete = await callback_query.message.edit_reply_markup(reply_markup=None)

    # Отображение сообщения о загрузке
    loading_message = await callback_query.message.answer("Загрузка результата...")

    user_data = await state.get_data()
    keyword = user_data.get('keyword')
    google_search_type = user_data.get('google_search_type', 'normal')
    next_index = user_data.get('next_index')

    if next_index:
        results, next_index = await google_search(keyword, YOUR_CSE_ID, start_index=next_index,
                                                  search_type=google_search_type)

        if not results:
            await loading_message.edit_text("Загрузка результатов не дала результатов.")
            await asyncio.sleep(0.5)
            await loading_message.delete()
            await message_to_delete.delete()
            await show_menu(callback_query.message)
            await state.finish()
            return

        if google_search_type == "images":
            image_urls = [item['link'] for item in results]
            valid_images = await prepare_images(image_urls)
            if valid_images:
                await bot.send_media_group(callback_query.message.chat.id, media=valid_images)
            else:
                await loading_message.edit_text("Не удалось загрузить изображения.")
        else:
            response_message = "\n".join([f"{item['title']}\n{item['link']}" for item in results])
            await callback_query.message.answer(response_message, disable_web_page_preview=True)

        await loading_message.edit_text("Загрузка успешно выполнена.")
        await asyncio.sleep(0.5)
        await loading_message.delete()
        await message_to_delete.delete()

        # Проверяем, есть ли еще результаты для показа
        if next_index:
            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton("Да", callback_data="get_more_google"),
                InlineKeyboardButton("Нет", callback_data="no_more_google")
            )
            show_more_message = await callback_query.message.answer("Показать еще результаты?", reply_markup=markup)
            await state.update_data(next_index=next_index, last_message_id=show_more_message.message_id)
        else:
            await callback_query.message.answer("Больше результатов нет.")
            await show_menu(callback_query.message)
            await state.finish()
    else:
        await loading_message.edit_text("Больше результатов нет.")
        await asyncio.sleep(0.5)
        await loading_message.delete()
        await message_to_delete.delete()
        await show_menu(callback_query.message)
        await state.finish()


@dp.callback_query_handler(lambda query: query.data == "no_more_google",
                           state=MyStates.waiting_for_google_search_keyword)
async def no_more_google(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.delete()

    # Отправляем сообщение об окончании поиска
    await callback_query.message.answer("Поиск завершен.")
    # Завершаем текущее состояние поиска
    await state.finish()
    # Возвращаем пользователя в главное меню
    await start(callback_query.message, state)


def generate_similar_queries(query):
    # Example synonym mapping
    synonyms = {
        "example": ["sample", "instance", "illustration"]
    }
    similar_queries = [query]  # Include the original query

    # Append synonyms to the list of queries if available
    for synonym in synonyms.get(query, []):
        similar_queries.append(synonym)

    return similar_queries

# ____________________________________________telegraph_________________________________________________________________________________________________
@dp.message_handler(state=MyStates.waiting_for_telegraph_keyword)
async def process_keyword(message: types.Message, state: FSMContext):
    query = message.text
    query = cyrillic_to_latin(query)
    await message.delete()  # Удаляем сообщение с ключевым словом
    bot = dp.bot  # Получаем объект бота из контекста
    urls = await find_telegraph_pages(query, message, state, bot)  # Передаем объект бота в функцию
    if urls:
        await message.answer(f"Найдено {len(urls)} ссылок.")
        await send_links_in_parts(message, urls, state)
    else:
        await message.answer("Ссылки не найдены. Возвращаем вас в главное меню.")
        await start(message, state)  # Возвращаем пользователя на главный экран


@dp.callback_query_handler(lambda query: query.data == "telegram", state="*")
async def choose_telegram_search_type(query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Обычный 🌐", callback_data="with_photos"),
        InlineKeyboardButton("Фотографии 🖼️", callback_data="all"),
        InlineKeyboardButton("Назад ↩️", callback_data="back_so_vk")
    )
    await query.message.answer("Выберите тип поиска на telegra.ph:", reply_markup=keyboard)
    await SearchType.choosing_search_type.set()
    await query.answer(text="", show_alert=True)


@dp.callback_query_handler(lambda query: query.data in ["with_photos", "all"], state=SearchType.choosing_search_type)
async def telegraph_search_type_chosen(query: types.CallbackQuery, state: FSMContext):
    search_type = query.data
    await state.update_data(search_type=search_type)
    await query.message.delete()
    await choose_year(query, state)  # Переходим к выбору года


@dp.callback_query_handler(lambda query: query.data == "telegraph", state="*")
async def telegraph_search_start(query: CallbackQuery, state: FSMContext):
    user_id = query.from_user.id

    # Проверяем количество оставшихся запросов
    remaining_requests = get_remaining_requests(user_id)
    if remaining_requests == 0:
        await query.answer("У вас закончились доступные запросы на сегодня.")
        return

    # Уменьшаем лимит запросов пользователя, если у него остались запросы
    if update_request_limit(user_id):
        update_request_limit(user_id)
        # Если оставшиеся запросы есть, продолжаем выполнение действия
        keyboard = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Обычный 🌐", callback_data="all"),
            InlineKeyboardButton("Фотографии 🖼️", callback_data="with_photos"),
            InlineKeyboardButton("Назад ↩️", callback_data="back_so_vk")
        )
        await query.message.answer("Хотите искать все статьи или только с фотографиями?", reply_markup=keyboard)
        # Переход к состоянию выбора типа поиска необходимо добавить в класс состояний
        await SearchType.choosing_search_type.set()
        await query.answer(text="", show_alert=True)
    else:
        await query.answer("У вас закончились доступные запросы на сегодня.")


@dp.callback_query_handler(lambda query: query.data == "start_telegraph_search", state="*")
async def choose_year(query: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(row_width=2)
    for year in range(2015, 2025):
        keyboard.insert(InlineKeyboardButton(str(year), callback_data=f"year_{year}"))
    keyboard.insert(InlineKeyboardButton("Назад", callback_data="back"))
    await query.message.answer("Выберите год начала поиска:", reply_markup=keyboard)
    await SearchType.choosing_year.set()  # Устанавливаем состояние для выбора года


@dp.callback_query_handler(lambda query: query.data.startswith('year_'), state=SearchType.choosing_year)
async def handle_year_choice(query: CallbackQuery, state: FSMContext):
    chosen_year = int(query.data.split('_')[1])
    await state.update_data(start_year=chosen_year)
    await query.message.delete()
    message = await query.message.answer(
        f"Вы выбрали год: {chosen_year}. Теперь введите ключевое слово для поиска на telegra.ph:")
    await state.update_data(year_message_id=message.message_id)
    await MyStates.waiting_for_telegraph_keyword.set()  # Переходим к следующему состоянию


# Обработчик назад для выбора года
@dp.callback_query_handler(lambda query: query.data == "back", state=SearchType.choosing_year)
async def back_to_search_type(query: CallbackQuery):
    await query.message.delete()
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Обычный", callback_data="all"),
        InlineKeyboardButton("Фотографии", callback_data="with_photos")
    )
    await query.message.answer("Хотите искать статьи только с фотографиями или все?", reply_markup=keyboard)
    await SearchType.choosing_search_type.set()  # Переходим к выбору типа поиска


async def fetch_url(session, url, progress_callback, update_interval=10, search_type="all"):
    try:
        timeout = aiohttp.ClientTimeout(total=600)
        async with session.get(url, timeout=timeout) as response:
            # Проверяем, что статус ответа успешный
            if response.status in [200, 202]:  # Можно добавить другие статусы, которые считаются успешными
                content = await response.text()
                # Для поиска изображений используем BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                if search_type == "with_photos" and not soup.find('img'):
                    # Если изображений нет, сообщаем об этом
                    await progress_callback(url, False, update_interval)
                    return None
                # Если условия удовлетворены, сообщаем об успехе
                await progress_callback(url, True, update_interval)
                return url
            else:
                # Статус ответа не успех, сообщаем об этом
                await progress_callback(url, False, update_interval)
                return None
    except ClientError as e:
        # Логируем ошибку клиента и сообщаем о неудаче
        print(f"Ошибка при запросе {url}: {e}")
        await progress_callback(url, False, update_interval)
        return None
    except asyncio.TimeoutError:
        # Логируем ошибку таймаута и сообщаем о неудаче
        print(f"Таймаут при запросе {url}")
        await progress_callback(url, False, update_interval)
        return None

async def update_progress_message(progress_message, completed, total, current_query, force=False):
    if force or completed % max(1, total // 20) == 0:
        progress_percent = int((completed / total) * 100)
        progress_bar = "■" * (progress_percent // 10) + "□" * (10 - progress_percent // 10)
        progress_text = f"Поиск: {current_query}\nЗагрузка: [{progress_bar}] {progress_percent}%"
        try:
            await progress_message.edit_text(progress_text)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Ошибка при обновлении сообщения о прогрессе: {e}")

async def find_telegraph_pages(query: str, message: types.Message, state: FSMContext, bot: Bot) -> list:
    user_data = await state.get_data()
    chosen_year = user_data.get('start_year', 2015)
    search_type = user_data.get('search_type', 'all')
    current_year = datetime.now().year

    if chosen_year < 2015 or chosen_year > current_year:
        await message.answer(f"Выбран неверный год. Пожалуйста, выберите год от 2015 до {current_year}.")
        return []

    start_date = datetime(chosen_year, 1, 1)
    end_date = datetime(chosen_year, 12, 31)
    if chosen_year == current_year:
        end_date = datetime(current_year, datetime.now().month, datetime.now().day)

    total_days = (end_date - start_date).days + 1
    urls = []
    valid_urls = set()
    completed = 0

    try:
        user_data = await state.get_data()
        year_message_id = user_data.get('year_message_id')
        await bot.delete_message(message.chat.id, year_message_id)
    except Exception as e:
        print(f"Failed to delete progress message: {e}")

    async def progress_callback(url, found, update_interval):
        nonlocal completed
        if found:
            urls.append(url)
            if await check_page_content_for_exclusions(url, exclusion_list):
                valid_urls.add(url)
        completed += 1
        await update_progress_message(progress_message, completed, total_days, query, completed % update_interval == 0)

    progress_message = await bot.send_message(message.chat.id, "Загрузка началась...")
    await state.update_data(progress_message_id=progress_message.message_id, start_year=chosen_year)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for single_date in (start_date + timedelta(n) for n in range(total_days)):
            url = f"https://telegra.ph/{query}-{single_date.strftime('%m-%d')}"
            tasks.append(fetch_url(session, url, progress_callback, 10, search_type))

        await asyncio.gather(*tasks)

    await update_progress_message(progress_message, completed, total_days, query, True)

    return list(valid_urls)


# Функция транслитерации кириллических символов в латинские
def cyrillic_to_latin(text):
    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', ' ': '-', '-': '', '_': '',
        ',': '', '.': '', '«': '', '»': '', '—': '', '?': '', '!': '', '@': '', '#': '',
        '$': '', '%': '', '^': '', '&': '', '*': '', '(': '', ')': '', '=': '', '+': '',
        ';': '', ':': '', '\'': '', '"': '', '\\': '', '/': '', '|': '', '[': '', ']': '',
        '{': '', '}': '', '<': '', '>': '', '№': ''
    }
    return ''.join(translit_dict.get(char, char) for char in text.lower())


# Обработчик нажатия кнопки "Получить еще"
@dp.callback_query_handler(text="get_more", state=MyStates.sending_links)
async def get_more_links(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    urls = data.get('urls', [])
    current_position = data.get('current_position', 0)
    current_page = data.get('current_page', 1)
    part_size = 10  # Размер части, которую отправляем за раз

    if current_position < len(urls):
        end_position = min(current_position + part_size, len(urls))
        next_links_text = f"Список ссылок №{current_page + 1}"
        await state.update_data(current_page=current_page + 1)
        await send_next_links(callback_query.message, state, next_links_text)
        await state.update_data(current_position=end_position)

        if end_position >= len(urls):
            await callback_query.message.edit_reply_markup()
        await callback_query.answer()
    else:
        await callback_query.answer("Больше ссылок нет.")

# Обработчик завершения отправки ссылок
@dp.callback_query_handler(lambda query: query.data == "no_more", state=MyStates.sending_links)
async def no_more_links(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id, text="", show_alert=False)
    previous_message_id = (await state.get_data()).get('previous_message_id')
    if previous_message_id:
        await bot.delete_message(callback_query.message.chat.id, previous_message_id)
    await callback_query.message.delete()
    await start(callback_query.message, state)
    await state.finish()

async def check_page_content_for_exclusions(url, exclusion_list):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                content = await response.text()
                for exclusion in exclusion_list:
                    if exclusion in content:
                        return False
                return True
        except Exception as e:
            print(f"Ошибка при проверке контента страницы {url}: {e}")
            return False

async def send_next_links(message: types.Message, state: FSMContext, next_links_text: str):
    user_data = await state.get_data()
    urls = user_data.get('urls', [])
    current_position = user_data.get('current_position', 0)
    sent_urls_count = 0  # Счётчик успешно отправленных URL

    while sent_urls_count < 10 and current_position < len(urls):
        url = urls[current_position]
        if url not in sent_telegraph_links and await check_page_content_for_exclusions(url, exclusion_list):
            try:
                await message.answer(url)
                sent_telegraph_links.add(url)  # Добавляем URL в множество отправленных
                sent_urls_count += 1
            except RetryAfter as e:
                await asyncio.sleep(e.timeout)  # Ожидаем указанное время перед следующей попыткой
                # Повторяем попытку отправки сообщения после задержки
                await message.answer(url)
                sent_telegraph_links.add(url)
                sent_urls_count += 1
        current_position += 1

    # Обновляем текущую позицию в состоянии
    await state.update_data(current_position=current_position)

    # Если после прохода есть ещё URL для отправки, предлагаем пользователю показать ещё
    if current_position < len(urls):
        # Добавление кнопок "Да" и "Нет"
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Да", callback_data="get_more"),
            InlineKeyboardButton("Нет", callback_data="no_more")
        )
        await message.answer(next_links_text, reply_markup=markup)
        await MyStates.sending_links.set()
    else:
        await message.answer("Все ссылки отправлены.")
        await state.finish()
        # Отображение главного меню
        await start(message, state)

async def send_links_in_parts(message: Message, urls: list, state: FSMContext):
    await state.update_data(urls=urls, current_position=0)
    current_page = 1  # начинаем с первой страницы
    next_links_text = f"Список ссылок №{current_page}"  # формируем текст для первой страницы
    await state.update_data(current_page=current_page)
    await send_next_links(message, state, next_links_text)

@dp.callback_query_handler(lambda query: query.data == "get_more", state=MyStates.sending_links)
async def get_more_links(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_page = data.get('current_page', 1) + 1
    await state.update_data(current_page=current_page)
    next_links_text = f"Список ссылок №{current_page}"
    await send_next_links(callback_query.message, state, next_links_text)
    await callback_query.answer()

@dp.message_handler(state=MyStates.waiting_for_telegraph_keyword)
async def process_keyword(message: types.Message, state: FSMContext):
    query = message.text
    query = cyrillic_to_latin(query)
    await message.delete()  # Удаляем сообщение с ключевым словом
    bot = dp.bot  # Получаем объект бота из контекста
    urls = await find_telegraph_pages(query, message, state, bot)  # Передаем объект бота в функцию
    if urls:
        await message.answer(f"Найдено {len(urls)} ссылок.")
        await send_links_in_parts(message, urls, state)
    else:
        await message.answer("Ссылки не найдены. Возвращаем вас в главное меню.")
        await start(message, state)  # Возвращаем пользователя на главный экран



async def main():
    await dp.start_polling()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
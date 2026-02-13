"""
ПОЛНЫЙ КОД БОТА ДЛЯ RENDER.COM
Версия: 2.0 - ИСПРАВЛЕНА ОШИБКА ПОТОКОВ
Описание: Покерный бот SNAP DONK POKER KLUB с регистрацией, админ-панелью и управлением админами
Flask-сервер для поддержания работы на бесплатном тарифе Render
"""

# ============ ИМПОРТЫ ============
import os
import sys
import json
import logging
import threading
import sqlite3
from datetime import datetime
from flask import Flask, jsonify

# Импорты aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============ НАСТРОЙКА ЛОГИРОВАНИЯ ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ FLASK ПРИЛОЖЕНИЕ ============
app = Flask(__name__)

# ============ КОНФИГУРАЦИЯ ============
# Файлы для хранения настроек
CONFIG_FILE = "bot_settings.json"
ADMINS_FILE = "bot_admins.json"

# Токен берем из переменных окружения Render (обязательно!)
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN не найден в переменных окружения!")
    logger.error("Добавьте переменную TELEGRAM_TOKEN в настройках Render")
    sys.exit(1)

# ============ НАСТРОЙКИ ПО УМОЛЧАНИЮ ============
DEFAULT_SETTINGS = {
    "club_name": "SNAP DONK POKER KLUB",
    "rules_url": "https://telegra.ph/Reglament-pokernogo-kluba-SNAP-DONK-01-01",
    "tournament_date": "15 марта 2024",
    "tournament_time": "19:00",
    "tournament_buyin": "2000₽",
    "tournament_location": "ул. Покерная, д. 1",
    "club_description": "Лучший покерный клуб в городе!",
    "contact_info": "@club_administrator"
}

# ============ ГЛАВНЫЙ АДМИН ============
# 🔴 ВАЖНО: УКАЖИТЕ СВОЙ TELEGRAM ID ЗДЕСЬ!
SUPER_ADMIN_ID = 1043425588  # ЗАМЕНИТЕ НА СВОЙ ID!

# ============ ФУНКЦИИ ДЛЯ РАБОТЫ С АДМИНАМИ ============
def load_admins():
    """Загружает список админов из JSON файла"""
    if os.path.exists(ADMINS_FILE):
        try:
            with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("admins", [])
        except:
            return [SUPER_ADMIN_ID]
    else:
        save_admins([SUPER_ADMIN_ID])
        return [SUPER_ADMIN_ID]

def save_admins(admin_list):
    """Сохраняет список админов в JSON файл"""
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"admins": admin_list}, f, ensure_ascii=False, indent=4)

def add_admin(user_id):
    """Добавляет нового админа"""
    admins = load_admins()
    if user_id not in admins and user_id != SUPER_ADMIN_ID:
        admins.append(user_id)
        save_admins(admins)
        return True
    return False

def remove_admin(user_id):
    """Удаляет админа (нельзя удалить главного админа)"""
    if user_id == SUPER_ADMIN_ID:
        return False
    admins = load_admins()
    if user_id in admins:
        admins.remove(user_id)
        save_admins(admins)
        return True
    return False

def is_admin(user_id):
    """Проверяет, является ли пользователь админом"""
    return user_id == SUPER_ADMIN_ID or user_id in load_admins()

def is_super_admin(user_id):
    """Проверяет, является ли пользователь главным админом"""
    return user_id == SUPER_ADMIN_ID

def refresh_admins():
    """Обновляет глобальную переменную ADMIN_IDS"""
    global ADMIN_IDS
    ADMIN_IDS = load_admins()
    return ADMIN_IDS

# Загружаем админов
ADMIN_IDS = load_admins()

# ============ ФУНКЦИИ ДЛЯ РАБОТЫ С НАСТРОЙКАМИ КЛУБА ============
def load_settings():
    """Загружает настройки из JSON файла"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return DEFAULT_SETTINGS.copy()
    else:
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Сохраняет настройки в JSON файл"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def update_club_info(**kwargs):
    """Обновляет информацию о клубе"""
    settings = load_settings()
    for key, value in kwargs.items():
        if key in settings:
            settings[key] = value
    save_settings(settings)
    
    # Обновляем глобальные переменные
    global CLUB_NAME, RULES_URL, TOURNAMENT_DATE, TOURNAMENT_TIME
    global TOURNAMENT_BUYIN, TOURNAMENT_LOCATION, CLUB_DESCRIPTION, CONTACT_INFO
    
    CLUB_NAME = settings["club_name"]
    RULES_URL = settings["rules_url"]
    TOURNAMENT_DATE = settings["tournament_date"]
    TOURNAMENT_TIME = settings["tournament_time"]
    TOURNAMENT_BUYIN = settings["tournament_buyin"]
    TOURNAMENT_LOCATION = settings["tournament_location"]
    CLUB_DESCRIPTION = settings["club_description"]
    CONTACT_INFO = settings["contact_info"]
    
    return settings

# Загружаем настройки
_settings = load_settings()
CLUB_NAME = _settings["club_name"]
RULES_URL = _settings["rules_url"]
TOURNAMENT_DATE = _settings["tournament_date"]
TOURNAMENT_TIME = _settings["tournament_time"]
TOURNAMENT_BUYIN = _settings["tournament_buyin"]
TOURNAMENT_LOCATION = _settings["tournament_location"]
CLUB_DESCRIPTION = _settings["club_description"]
CONTACT_INFO = _settings["contact_info"]

# ============ БАЗА ДАННЫХ ============
class Database:
    """Работа с базой данных SQLite"""
    
    def __init__(self):
        self.conn = sqlite3.connect('poker.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()
    
    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                birth_date TEXT,
                nickname TEXT,
                reg_date TEXT,
                agreed BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def add_registration(self, user_id, username, full_name, birth_date, nickname, agreed=True):
        reg_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO registrations 
                (user_id, username, full_name, birth_date, nickname, reg_date, agreed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, full_name, birth_date, nickname, reg_date, agreed))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка БД: {e}")
            return False
    
    def get_registration(self, user_id):
        self.cursor.execute('SELECT * FROM registrations WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def get_all_registrations(self):
        self.cursor.execute('SELECT * FROM registrations ORDER BY created_at DESC')
        return self.cursor.fetchall()
    
    def check_registered(self, user_id):
        self.cursor.execute('SELECT user_id FROM registrations WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None
    
    def get_registration_count(self):
        self.cursor.execute('SELECT COUNT(*) FROM registrations')
        return self.cursor.fetchone()[0]

db = Database()

# ============ СОСТОЯНИЯ FSM ============
class Registration(StatesGroup):
    """Состояния для регистрации пользователей"""
    full_name = State()
    birth_date = State()
    nickname = State()
    agreement = State()
    confirmation = State()

class AdminEdit(StatesGroup):
    """Состояния для редактирования информации клуба"""
    waiting_for_club_name = State()
    waiting_for_rules_url = State()
    waiting_for_tournament_date = State()
    waiting_for_tournament_time = State()
    waiting_for_buyin = State()
    waiting_for_location = State()
    waiting_for_description = State()
    waiting_for_contact = State()

class AdminManagement(StatesGroup):
    """Состояния для управления администраторами"""
    waiting_for_new_admin_id = State()
    waiting_for_remove_admin_id = State()

# ============ КЛАВИАТУРЫ ============
def get_start_keyboard():
    """Главное меню для всех пользователей"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="📝 ЗАРЕГИСТРИРОВАТЬСЯ НА ТУРНИР",
        callback_data="register"
    ))
    builder.add(InlineKeyboardButton(
        text="ℹ️ О КЛУБЕ",
        callback_data="about"
    ))
    builder.add(InlineKeyboardButton(
        text="📋 МОИ ДАННЫЕ",
        callback_data="my_data"
    ))
    builder.adjust(1)
    return builder.as_markup()

def get_agreement_keyboard():
    """Клавиатура для согласия с регламентом"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📜 РЕГЛАМЕНТ ИГРЫ И ПРАВИЛА КЛУБА",
        url=RULES_URL
    ))
    builder.row(InlineKeyboardButton(
        text="✅ Я ОЗНАКОМИЛСЯ И СОГЛАШАЮСЬ",
        callback_data="agree"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ ОТМЕНИТЬ",
        callback_data="cancel"
    ))
    return builder.as_markup()

def get_confirm_keyboard():
    """Клавиатура подтверждения регистрации"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ ВСЁ ВЕРНО, ЗАВЕРШИТЬ РЕГИСТРАЦИЮ",
        callback_data="confirm"
    ))
    builder.add(InlineKeyboardButton(
        text="✏️ ЗАПОЛНИТЬ ЗАНОВО",
        callback_data="register"
    ))
    builder.adjust(1)
    return builder.as_markup()

def get_admin_main_keyboard(is_super=False):
    """Главное меню админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="📊 ПОКАЗАТЬ ВСЕХ УЧАСТНИКОВ",
        callback_data="admin_list"
    ))
    builder.add(InlineKeyboardButton(
        text="✏️ РЕДАКТИРОВАТЬ ИНФОРМАЦИЮ",
        callback_data="admin_edit_menu"
    ))
    builder.add(InlineKeyboardButton(
        text="📎 ЭКСПОРТ В TXT",
        callback_data="admin_export"
    ))
    if is_super:
        builder.add(InlineKeyboardButton(
            text="👥 УПРАВЛЕНИЕ АДМИНАМИ",
            callback_data="admin_manage"
        ))
    builder.add(InlineKeyboardButton(
        text="🔄 В ГЛАВНОЕ МЕНЮ",
        callback_data="back_to_start"
    ))
    builder.adjust(1)
    return builder.as_markup()

def get_admin_edit_keyboard():
    """Меню редактирования информации клуба"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🏆 НАЗВАНИЕ КЛУБА",
        callback_data="admin_edit_club_name"
    ))
    builder.add(InlineKeyboardButton(
        text="🔗 ССЫЛКА НА РЕГЛАМЕНТ",
        callback_data="admin_edit_rules"
    ))
    builder.add(InlineKeyboardButton(
        text="📅 ДАТА ТУРНИРА",
        callback_data="admin_edit_date"
    ))
    builder.add(InlineKeyboardButton(
        text="⏰ ВРЕМЯ ТУРНИРА",
        callback_data="admin_edit_time"
    ))
    builder.add(InlineKeyboardButton(
        text="💰 БАЙ-ИН",
        callback_data="admin_edit_buyin"
    ))
    builder.add(InlineKeyboardButton(
        text="📍 МЕСТО ПРОВЕДЕНИЯ",
        callback_data="admin_edit_location"
    ))
    builder.add(InlineKeyboardButton(
        text="📝 ОПИСАНИЕ КЛУБА",
        callback_data="admin_edit_description"
    ))
    builder.add(InlineKeyboardButton(
        text="📞 КОНТАКТЫ",
        callback_data="admin_edit_contact"
    ))
    builder.add(InlineKeyboardButton(
        text="◀️ НАЗАД",
        callback_data="admin_back"
    ))
    builder.adjust(1)
    return builder.as_markup()

def get_admin_management_keyboard():
    """Меню управления администраторами"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="➕ ДОБАВИТЬ АДМИНА",
        callback_data="admin_add"
    ))
    builder.add(InlineKeyboardButton(
        text="➖ УДАЛИТЬ АДМИНА",
        callback_data="admin_remove"
    ))
    builder.add(InlineKeyboardButton(
        text="📋 СПИСОК АДМИНОВ",
        callback_data="admin_list_admins"
    ))
    builder.add(InlineKeyboardButton(
        text="◀️ НАЗАД",
        callback_data="admin_back"
    ))
    builder.adjust(1)
    return builder.as_markup()

def get_admin_back_keyboard():
    """Кнопка возврата в админ-панель"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="◀️ В АДМИН-ПАНЕЛЬ",
        callback_data="admin_back"
    ))
    return builder.as_markup()

def get_cancel_keyboard():
    """Кнопка отмены действия"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="❌ ОТМЕНИТЬ",
        callback_data="admin_cancel"
    ))
    return builder.as_markup()

# ============ ИНИЦИАЛИЗАЦИЯ БОТА ============
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============ ОБРАБОТЧИКИ КОМАНД ============

# ---------- СТАРТ ----------
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Приветствие и главное меню"""
    user_name = message.from_user.first_name
    
    welcome_text = f"""
🎰 <b>ДОБРО ПОЖАЛОВАТЬ В {CLUB_NAME}!</b> 🎰

Привет, {user_name}! 👋

<b>С помощью этого бота ты можешь:</b>
✅ Зарегистрироваться на покерный турнир
✅ Ознакомиться с регламентом клуба
✅ Посмотреть свои регистрационные данные
✅ Получить информацию о ближайших турнирах

<b>Выбери действие в меню ниже:</b>
👇👇👇
    """
    
    await message.answer(
        welcome_text,
        reply_markup=get_start_keyboard(),
        parse_mode="HTML"
    )
    
    logger.info(f"User @{message.from_user.username} ({message.from_user.id}) started bot")

# ---------- ИНФОРМАЦИЯ О КЛУБЕ ----------
@dp.callback_query(F.data == "about")
async def about_club(callback: types.CallbackQuery):
    """Информация о клубе и ближайшем турнире"""
    text = f"""
🏆 <b>{CLUB_NAME}</b> 🏆

━━━━━━━━━━━━━━━━━━━━━
<b>🎯 БЛИЖАЙШИЙ ТУРНИР</b>
━━━━━━━━━━━━━━━━━━━━━

📅 <b>Дата:</b> {TOURNAMENT_DATE}
⏰ <b>Время:</b> {TOURNAMENT_TIME}
💰 <b>Бай-ин:</b> {TOURNAMENT_BUYIN}
📍 <b>Адрес:</b> {TOURNAMENT_LOCATION}
📝 <b>Регистрация:</b> до 23:59 дня турнира

━━━━━━━━━━━━━━━━━━━━━
<b>📋 ФОРМАТ ТУРНИРА</b>
━━━━━━━━━━━━━━━━━━━━━

• Техасский Холдем (No Limit)
• Блайнды: 20 минут
• Стартовый стек: 5000 фишек
• Реэнтри: до 5 уровня
• Призовой фонд: 70% от бай-инов

━━━━━━━━━━━━━━━━━━━━━
<b>⚖️ ПРАВИЛА КЛУБА</b>
━━━━━━━━━━━━━━━━━━━━━

🔹 Игроки должны быть старше 18 лет
🔹 Запрещены оскорбления и неспортивное поведение
🔹 Решение дилера является окончательным
🔹 {CLUB_DESCRIPTION}

━━━━━━━━━━━━━━━━━━━━━
📜 <a href="{RULES_URL}">ПОЛНЫЙ ТЕКСТ РЕГЛАМЕНТА</a>
━━━━━━━━━━━━━━━━━━━━━

📞 <b>Контакты:</b> {CONTACT_INFO}
    """
    
    await callback.message.answer(
        text,
        reply_markup=get_start_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()

# ---------- НАЧАЛО РЕГИСТРАЦИИ ----------
@dp.callback_query(F.data == "register")
async def start_registration(callback: types.CallbackQuery, state: FSMContext):
    """Запуск процесса регистрации"""
    
    if db.check_registered(callback.from_user.id):
        await callback.message.answer(
            "⚠️ <b>Вы уже зарегистрированы на турнир!</b>\n\n"
            "Ваши данные сохранены в системе.\n"
            "Если нужно изменить информацию - обратитесь к администратору.",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.answer(
        "📝 <b>РЕГИСТРАЦИЯ НА ТУРНИР</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Шаг 1 из 4</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✏️ <b>Введите ваше ФИО полностью:</b>\n"
        "└ <i>Пример: Иванов Иван Иванович</i>\n\n"
        "❗️ Минимум: Имя и Фамилия",
        parse_mode="HTML"
    )
    
    await state.set_state(Registration.full_name)
    await callback.answer()

# ---------- ОБРАБОТКА ФИО ----------
@dp.message(Registration.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    """Принимает и валидирует ФИО"""
    
    full_name = message.text.strip()
    words = full_name.split()
    
    if len(words) < 2:
        await message.answer(
            "❌ <b>Ошибка ввода</b>\n\n"
            "Пожалуйста, введите Имя и Фамилию.\n"
            "Пример: <i>Иванов Иван</i>\n\n"
            "Попробуйте снова:",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(full_name=full_name)
    
    await message.answer(
        "📅 <b>Шаг 2 из 4</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🗓 <b>Введите дату рождения:</b>\n"
        "└ <i>Формат: ДД.ММ.ГГГГ</i>\n"
        "└ <i>Пример: 15.05.1990</i>\n\n"
        "⚠️ <b>Важно:</b> Регистрация доступна только с 18 лет",
        parse_mode="HTML"
    )
    
    await state.set_state(Registration.birth_date)

# ---------- ОБРАБОТКА ДАТЫ РОЖДЕНИЯ ----------
@dp.message(Registration.birth_date)
async def process_birth_date(message: types.Message, state: FSMContext):
    """Принимает и валидирует дату рождения"""
    
    date_text = message.text.strip()
    
    try:
        day, month, year = map(int, date_text.split('.'))
        birth_date = datetime(year, month, day)
        
        today = datetime.now()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        if age < 18:
            await message.answer(
                "❌ <b>Регистрация недоступна</b>\n\n"
                "К сожалению, вам меньше 18 лет.\n"
                "Повторите ввод даты рождения:",
                parse_mode="HTML"
            )
            return
            
    except (ValueError, IndexError):
        await message.answer(
            "❌ <b>Неверный формат даты</b>\n\n"
            "Используйте формат: <i>ДД.ММ.ГГГГ</i>\n"
            "Пример: <i>15.05.1990</i>\n\n"
            "Попробуйте снова:",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(birth_date=date_text)
    
    await message.answer(
        "🎭 <b>Шаг 3 из 4</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✏️ <b>Введите ваш покерный псевдоним (ник):</b>\n"
        "└ <i>Как вас будут называть за столом</i>\n"
        "└ <i>Пример: SnapDonkPro, PokerKing, LuckyFish</i>\n\n"
        "❗️ Минимум 2 символа",
        parse_mode="HTML"
    )
    
    await state.set_state(Registration.nickname)

# ---------- ОБРАБОТКА ПОКЕРНОГО НИКА ----------
@dp.message(Registration.nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    """Принимает и валидирует покерный псевдоним"""
    
    nickname = message.text.strip()
    
    if len(nickname) < 2:
        await message.answer(
            "❌ <b>Слишком короткий ник</b>\n\n"
            "Минимальная длина: 2 символа\n"
            "Попробуйте снова:",
            parse_mode="HTML"
        )
        return
    
    forbidden_chars = '@#$%^&*()+='
    if any(char in nickname for char in forbidden_chars):
        await message.answer(
            "❌ <b>Недопустимые символы</b>\n\n"
            "Ник может содержать буквы, цифры и символы: _ - .\n"
            "Запрещены: @ # $ % ^ & * ( ) + =\n\n"
            "Попробуйте снова:",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(nickname=nickname)
    
    agreement_text = f"""
⚖️ <b>Шаг 4 из 4 - ПОДТВЕРЖДЕНИЕ ПРАВИЛ</b>

━━━━━━━━━━━━━━━━━━━━━

<b>Для завершения регистрации необходимо:</b>

1️⃣ <b>ОЗНАКОМИТЬСЯ</b> с регламентом клуба
2️⃣ <b>ПОДТВЕРДИТЬ</b> свое согласие

━━━━━━━━━━━━━━━━━━━━━
🔗 <a href="{RULES_URL}">📜 ОТКРЫТЬ РЕГЛАМЕНТ</a>
━━━━━━━━━━━━━━━━━━━━━
    """
    
    await message.answer(
        agreement_text,
        reply_markup=get_agreement_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await state.set_state(Registration.agreement)

# ---------- ПОДТВЕРЖДЕНИЕ СОГЛАСИЯ ----------
@dp.callback_query(F.data == "agree")
async def process_agreement(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение согласия с регламентом"""
    
    await state.update_data(agreed=True)
    data = await state.get_data()
    
    preview_text = f"""
✅ <b>ПРОВЕРЬТЕ ВВЕДЕННЫЕ ДАННЫЕ:</b>

━━━━━━━━━━━━━━━━━━━━━
👤 <b>ФИО:</b> {data.get('full_name')}
📅 <b>Дата рождения:</b> {data.get('birth_date')}
🎭 <b>Псевдоним:</b> {data.get('nickname')}
━━━━━━━━━━━━━━━━━━━━━
📋 <b>Статус согласия:</b> ✅ ПОДТВЕРЖДЕНО
━━━━━━━━━━━━━━━━━━━━━

<b>Всё верно?</b>
    """
    
    await callback.message.answer(
        preview_text,
        reply_markup=get_confirm_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
    await state.set_state(Registration.confirmation)

# ---------- ОТМЕНА РЕГИСТРАЦИИ ----------
@dp.callback_query(F.data == "cancel")
async def cancel_registration(callback: types.CallbackQuery, state: FSMContext):
    """Отмена регистрации"""
    
    await state.clear()
    await callback.message.answer(
        "❌ <b>Регистрация отменена</b>\n\n"
        "Вы можете начать заново в любой момент.",
        reply_markup=get_start_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# ---------- ПОДТВЕРЖДЕНИЕ РЕГИСТРАЦИИ ----------
@dp.callback_query(F.data == "confirm")
async def confirm_registration(callback: types.CallbackQuery, state: FSMContext):
    """Финализация регистрации"""
    
    data = await state.get_data()
    
    success = db.add_registration(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=data.get('full_name'),
        birth_date=data.get('birth_date'),
        nickname=data.get('nickname')
    )
    
    if success:
        reg_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        final_text = f"""
🎉 <b>РЕГИСТРАЦИЯ УСПЕШНО ЗАВЕРШЕНА!</b> 🎉

━━━━━━━━━━━━━━━━━━━━━
🏆 <b>{CLUB_NAME}</b> 
━━━━━━━━━━━━━━━━━━━━━

<b>Ваши данные:</b>
👤 <b>ФИО:</b> {data.get('full_name')}
📅 <b>Дата рождения:</b> {data.get('birth_date')}
🎭 <b>Псевдоним:</b> {data.get('nickname')}
📆 <b>Дата регистрации:</b> {reg_time}

━━━━━━━━━━━━━━━━━━━━━
✅ <b>Согласие с регламентом:</b> ПОДТВЕРЖДЕНО
━━━━━━━━━━━━━━━━━━━━━

🔔 <b>Напоминание о турнире:</b>
📅 Дата: {TOURNAMENT_DATE}
⏰ Время: {TOURNAMENT_TIME}
📍 Адрес: {TOURNAMENT_LOCATION}
💰 Бай-ин: {TOURNAMENT_BUYIN}

🃏 <b>Желаем удачи!</b> ♠️♥️♦️♣️
        """
        
        await callback.message.answer(
            final_text,
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
        
        # Уведомление админов
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"✅ <b>НОВАЯ РЕГИСТРАЦИЯ!</b>\n\n"
                         f"👤 {data.get('full_name')}\n"
                         f"🎭 {data.get('nickname')}\n"
                         f"🆔 @{callback.from_user.username}\n"
                         f"📅 {reg_time}",
                    parse_mode="HTML"
                )
            except:
                pass
        
        logger.info(f"New registration: {data.get('full_name')}")
    else:
        await callback.message.answer(
            "❌ <b>Ошибка при сохранении</b>\n\n"
            "Пожалуйста, попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
    
    await state.clear()
    await callback.answer()

# ---------- ПРОСМОТР СВОИХ ДАННЫХ ----------
@dp.callback_query(F.data == "my_data")
async def show_my_data(callback: types.CallbackQuery):
    """Показывает данные пользователя"""
    
    registration = db.get_registration(callback.from_user.id)
    
    if not registration:
        await callback.message.answer(
            "❌ <b>Вы ещё не зарегистрированы</b>\n\n"
            "Нажмите кнопку ниже для регистрации 👇",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
    else:
        (_, _, _, full_name, birth_date, nickname, reg_date, _, _) = registration
        
        text = f"""
📋 <b>ВАША РЕГИСТРАЦИЯ:</b>

━━━━━━━━━━━━━━━━━━━━━
👤 <b>ФИО:</b> {full_name}
📅 <b>Дата рождения:</b> {birth_date}
🎭 <b>Псевдоним:</b> {nickname}
📆 <b>Дата регистрации:</b> {reg_date}
━━━━━━━━━━━━━━━━━━━━━
✅ <b>Согласие:</b> ПОДТВЕРЖДЕНО
━━━━━━━━━━━━━━━━━━━━━

📜 <a href="{RULES_URL}">Открыть регламент</a>
        """
        
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_start_keyboard(),
            disable_web_page_preview=True
        )
    
    await callback.answer()

# ---------- АДМИН-ПАНЕЛЬ ----------
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Панель администратора"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ <b>Доступ запрещен</b>", parse_mode="HTML")
        return
    
    stats = db.get_all_registrations()
    is_super = is_super_admin(message.from_user.id)
    
    text = f"""
🔐 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>
━━━━━━━━━━━━━━━━━━━━━

📊 <b>СТАТИСТИКА:</b>
• Всего регистраций: {len(stats)}

{'👑 <b>РОЛЬ:</b> ГЛАВНЫЙ АДМИН' if is_super else '👤 <b>РОЛЬ:</b> АДМИН'}

━━━━━━━━━━━━━━━━━━━━━
🏆 <b>ТЕКУЩАЯ ИНФОРМАЦИЯ:</b>

<b>Название:</b> {CLUB_NAME}
<b>Дата турнира:</b> {TOURNAMENT_DATE} {TOURNAMENT_TIME}
<b>Бай-ин:</b> {TOURNAMENT_BUYIN}
━━━━━━━━━━━━━━━━━━━━━
    """
    
    await message.answer(
        text,
        reply_markup=get_admin_main_keyboard(is_super),
        parse_mode="HTML"
    )

# ---------- ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ----------
@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    await cmd_start(callback.message)
    await callback.answer()

# ---------- МЕНЮ РЕДАКТИРОВАНИЯ ----------
@dp.callback_query(F.data == "admin_edit_menu")
async def admin_edit_menu(callback: types.CallbackQuery):
    """Меню редактирования информации"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "✏️ <b>РЕДАКТИРОВАНИЕ ИНФОРМАЦИИ</b>\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=get_admin_edit_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# ---------- УПРАВЛЕНИЕ АДМИНАМИ ----------
@dp.callback_query(F.data == "admin_manage")
async def admin_manage(callback: types.CallbackQuery):
    """Меню управления администраторами"""
    
    if not is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Только главный админ может управлять админами!", show_alert=True)
        return
    
    await callback.message.answer(
        "👥 <b>УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ</b>",
        reply_markup=get_admin_management_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# ---------- СПИСОК АДМИНОВ ----------
@dp.callback_query(F.data == "admin_list_admins")
async def admin_list_admins(callback: types.CallbackQuery):
    """Показывает список всех администраторов"""
    
    if not is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    admins = load_admins()
    
    text = "👥 <b>СПИСОК АДМИНИСТРАТОРОВ:</b>\n\n"
    text += f"👑 <b>Главный админ:</b> <code>{SUPER_ADMIN_ID}</code>\n\n"
    text += "<b>Администраторы:</b>\n"
    
    admin_list = [admin_id for admin_id in admins if admin_id != SUPER_ADMIN_ID]
    if admin_list:
        for i, admin_id in enumerate(admin_list, 1):
            text += f"{i}. <code>{admin_id}</code>\n"
    else:
        text += "Нет других администраторов\n"
    
    text += f"\nВсего админов: {len(admins)}"
    
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_management_keyboard()
    )
    await callback.answer()

# ---------- ДОБАВЛЕНИЕ АДМИНА ----------
@dp.callback_query(F.data == "admin_add")
async def admin_add(callback: types.CallbackQuery, state: FSMContext):
    """Добавление администратора"""
    
    if not is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "➕ <b>ДОБАВЛЕНИЕ АДМИНИСТРАТОРА</b>\n\n"
        "Введите Telegram ID пользователя:\n\n"
        "<i>Как узнать ID: @userinfobot</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminManagement.waiting_for_new_admin_id)
    await callback.answer()

@dp.message(AdminManagement.waiting_for_new_admin_id)
async def process_add_admin(message: types.Message, state: FSMContext):
    """Обработка добавления админа"""
    
    if not is_super_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    try:
        new_admin_id = int(message.text.strip())
        
        if new_admin_id == SUPER_ADMIN_ID:
            await message.answer(
                "❌ Это главный администратор!",
                reply_markup=get_admin_management_keyboard()
            )
        elif add_admin(new_admin_id):
            refresh_admins()
            await message.answer(
                f"✅ <b>Администратор добавлен!</b>\n\nID: <code>{new_admin_id}</code>",
                parse_mode="HTML",
                reply_markup=get_admin_management_keyboard()
            )
            try:
                await bot.send_message(
                    chat_id=new_admin_id,
                    text=f"🎉 Вы назначены администратором бота {CLUB_NAME}!",
                    parse_mode="HTML"
                )
            except:
                pass
        else:
            await message.answer(
                "❌ Этот пользователь уже является администратором!",
                reply_markup=get_admin_management_keyboard()
            )
    except ValueError:
        await message.answer(
            "❌ Неверный формат ID. ID должен быть числом.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.clear()

# ---------- УДАЛЕНИЕ АДМИНА ----------
@dp.callback_query(F.data == "admin_remove")
async def admin_remove(callback: types.CallbackQuery, state: FSMContext):
    """Удаление администратора"""
    
    if not is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    admins = load_admins()
    admin_list = [admin_id for admin_id in admins if admin_id != SUPER_ADMIN_ID]
    
    if not admin_list:
        await callback.message.answer(
            "❌ Нет других администраторов для удаления.",
            reply_markup=get_admin_management_keyboard()
        )
        await callback.answer()
        return
    
    admins_text = "\n".join([f"• <code>{admin_id}</code>" for admin_id in admin_list])
    
    await callback.message.answer(
        "➖ <b>УДАЛЕНИЕ АДМИНИСТРАТОРА</b>\n\n"
        f"<b>Текущие администраторы:</b>\n{admins_text}\n\n"
        "Введите ID администратора для удаления:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminManagement.waiting_for_remove_admin_id)
    await callback.answer()

@dp.message(AdminManagement.waiting_for_remove_admin_id)
async def process_remove_admin(message: types.Message, state: FSMContext):
    """Обработка удаления админа"""
    
    if not is_super_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    try:
        remove_id = int(message.text.strip())
        
        if remove_id == SUPER_ADMIN_ID:
            await message.answer(
                "❌ Невозможно удалить главного администратора!",
                reply_markup=get_admin_management_keyboard()
            )
        elif remove_admin(remove_id):
            refresh_admins()
            await message.answer(
                f"✅ <b>Администратор удален!</b>\n\nID: <code>{remove_id}</code>",
                parse_mode="HTML",
                reply_markup=get_admin_management_keyboard()
            )
            try:
                await bot.send_message(
                    chat_id=remove_id,
                    text=f"📋 Ваши права администратора бота {CLUB_NAME} отозваны.",
                    parse_mode="HTML"
                )
            except:
                pass
        else:
            await message.answer(
                "❌ Пользователь с таким ID не является администратором!",
                reply_markup=get_admin_management_keyboard()
            )
    except ValueError:
        await message.answer(
            "❌ Неверный формат ID. ID должен быть числом.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.clear()

# ---------- РЕДАКТИРОВАНИЕ НАЗВАНИЯ КЛУБА ----------
@dp.callback_query(F.data == "admin_edit_club_name")
async def admin_edit_club_name(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование названия клуба"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "🏆 <b>ИЗМЕНЕНИЕ НАЗВАНИЯ КЛУБА</b>\n\n"
        f"Текущее: <b>{CLUB_NAME}</b>\n\n"
        "Введите новое название:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminEdit.waiting_for_club_name)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_club_name)
async def process_new_club_name(message: types.Message, state: FSMContext):
    """Обработка нового названия клуба"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    new_name = message.text.strip()
    
    if len(new_name) < 3:
        await message.answer(
            "❌ Слишком короткое название. Минимум 3 символа.\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    update_club_info(club_name=new_name)
    
    await message.answer(
        f"✅ <b>Название клуба обновлено!</b>\n\nНовое название: <b>{new_name}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()

# ---------- РЕДАКТИРОВАНИЕ ССЫЛКИ НА РЕГЛАМЕНТ ----------
@dp.callback_query(F.data == "admin_edit_rules")
async def admin_edit_rules(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование ссылки на регламент"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "🔗 <b>ИЗМЕНЕНИЕ ССЫЛКИ НА РЕГЛАМЕНТ</b>\n\n"
        f"Текущая ссылка:\n<code>{RULES_URL}</code>\n\n"
        "Введите новую ссылку:\n"
        "<i>(должна начинаться с http:// или https://)</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminEdit.waiting_for_rules_url)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_rules_url)
async def process_new_rules_url(message: types.Message, state: FSMContext):
    """Обработка новой ссылки на регламент"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    new_url = message.text.strip()
    
    if not (new_url.startswith('http://') or new_url.startswith('https://')):
        await message.answer(
            "❌ Ссылка должна начинаться с http:// или https://",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    update_club_info(rules_url=new_url)
    
    await message.answer(
        "✅ <b>Ссылка на регламент обновлена!</b>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()

# ---------- РЕДАКТИРОВАНИЕ ДАТЫ ТУРНИРА ----------
@dp.callback_query(F.data == "admin_edit_date")
async def admin_edit_date(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование даты турнира"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "📅 <b>ИЗМЕНЕНИЕ ДАТЫ ТУРНИРА</b>\n\n"
        f"Текущая дата: <b>{TOURNAMENT_DATE}</b>\n\n"
        "Введите новую дату:\n"
        "<i>Пример: 20 апреля 2024</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminEdit.waiting_for_tournament_date)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_tournament_date)
async def process_new_date(message: types.Message, state: FSMContext):
    """Обработка новой даты турнира"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    new_date = message.text.strip()
    
    if len(new_date) < 5:
        await message.answer(
            "❌ Слишком короткая дата",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    update_club_info(tournament_date=new_date)
    
    await message.answer(
        f"✅ <b>Дата турнира обновлена!</b>\n\nНовая дата: <b>{new_date}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()

# ---------- РЕДАКТИРОВАНИЕ ВРЕМЕНИ ТУРНИРА ----------
@dp.callback_query(F.data == "admin_edit_time")
async def admin_edit_time(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование времени турнира"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "⏰ <b>ИЗМЕНЕНИЕ ВРЕМЕНИ ТУРНИРА</b>\n\n"
        f"Текущее время: <b>{TOURNAMENT_TIME}</b>\n\n"
        "Введите новое время:\n"
        "<i>Пример: 20:00</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminEdit.waiting_for_tournament_time)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_tournament_time)
async def process_new_time(message: types.Message, state: FSMContext):
    """Обработка нового времени турнира"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    new_time = message.text.strip()
    
    if ':' not in new_time:
        await message.answer(
            "❌ Неверный формат. Используйте ЧЧ:ММ",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    update_club_info(tournament_time=new_time)
    
    await message.answer(
        f"✅ <b>Время турнира обновлено!</b>\n\nНовое время: <b>{new_time}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()

# ---------- РЕДАКТИРОВАНИЕ БАЙ-ИНА ----------
@dp.callback_query(F.data == "admin_edit_buyin")
async def admin_edit_buyin(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование бай-ина"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "💰 <b>ИЗМЕНЕНИЕ БАЙ-ИНА</b>\n\n"
        f"Текущий бай-ин: <b>{TOURNAMENT_BUYIN}</b>\n\n"
        "Введите новый бай-ин:\n"
        "<i>Пример: 2500₽</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminEdit.waiting_for_buyin)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_buyin)
async def process_new_buyin(message: types.Message, state: FSMContext):
    """Обработка нового бай-ина"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    new_buyin = message.text.strip()
    
    if len(new_buyin) < 2:
        await message.answer(
            "❌ Слишком короткое значение",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    update_club_info(tournament_buyin=new_buyin)
    
    await message.answer(
        f"✅ <b>Бай-ин обновлен!</b>\n\nНовый бай-ин: <b>{new_buyin}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()

# ---------- РЕДАКТИРОВАНИЕ МЕСТА ПРОВЕДЕНИЯ ----------
@dp.callback_query(F.data == "admin_edit_location")
async def admin_edit_location(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование места проведения"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "📍 <b>ИЗМЕНЕНИЕ МЕСТА ПРОВЕДЕНИЯ</b>\n\n"
        f"Текущее место: <b>{TOURNAMENT_LOCATION}</b>\n\n"
        "Введите новое место:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminEdit.waiting_for_location)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_location)
async def process_new_location(message: types.Message, state: FSMContext):
    """Обработка нового места проведения"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    new_location = message.text.strip()
    
    if len(new_location) < 5:
        await message.answer(
            "❌ Слишком короткое название",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    update_club_info(tournament_location=new_location)
    
    await message.answer(
        f"✅ <b>Место проведения обновлено!</b>\n\nНовое место: <b>{new_location}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()

# ---------- РЕДАКТИРОВАНИЕ ОПИСАНИЯ КЛУБА ----------
@dp.callback_query(F.data == "admin_edit_description")
async def admin_edit_description(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование описания клуба"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "📝 <b>ИЗМЕНЕНИЕ ОПИСАНИЯ КЛУБА</b>\n\n"
        f"Текущее описание:\n<i>{CLUB_DESCRIPTION}</i>\n\n"
        "Введите новое описание:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminEdit.waiting_for_description)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_description)
async def process_new_description(message: types.Message, state: FSMContext):
    """Обработка нового описания клуба"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    new_description = message.text.strip()
    
    if len(new_description) < 10:
        await message.answer(
            "❌ Слишком короткое описание. Минимум 10 символов.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    update_club_info(club_description=new_description)
    
    await message.answer(
        "✅ <b>Описание клуба обновлено!</b>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()

# ---------- РЕДАКТИРОВАНИЕ КОНТАКТНОЙ ИНФОРМАЦИИ ----------
@dp.callback_query(F.data == "admin_edit_contact")
async def admin_edit_contact(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование контактной информации"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.answer(
        "📞 <b>ИЗМЕНЕНИЕ КОНТАКТНОЙ ИНФОРМАЦИИ</b>\n\n"
        f"Текущие контакты: <b>{CONTACT_INFO}</b>\n\n"
        "Введите новые контакты:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminEdit.waiting_for_contact)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_contact)
async def process_new_contact(message: types.Message, state: FSMContext):
    """Обработка новой контактной информации"""
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        await state.clear()
        return
    
    new_contact = message.text.strip()
    
    if len(new_contact) < 3:
        await message.answer(
            "❌ Слишком короткие контактные данные",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    update_club_info(contact_info=new_contact)
    
    await message.answer(
        f"✅ <b>Контакты обновлены!</b>\n\nНовые контакты: <b>{new_contact}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()

# ---------- ВОЗВРАТ В АДМИН-ПАНЕЛЬ ----------
@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    """Возврат в админ-панель"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_all_registrations()
    is_super = is_super_admin(callback.from_user.id)
    
    text = f"""
🔐 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>
━━━━━━━━━━━━━━━━━━━━━

📊 <b>СТАТИСТИКА:</b>
• Всего регистраций: {len(stats)}

{'👑 <b>РОЛЬ:</b> ГЛАВНЫЙ АДМИН' if is_super else '👤 <b>РОЛЬ:</b> АДМИН'}
━━━━━━━━━━━━━━━━━━━━━
    """
    
    await callback.message.answer(
        text,
        reply_markup=get_admin_main_keyboard(is_super),
        parse_mode="HTML"
    )
    await callback.answer()

# ---------- ОТМЕНА РЕДАКТИРОВАНИЯ ----------
@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена редактирования"""
    
    await state.clear()
    await callback.message.answer(
        "❌ Действие отменено",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# ---------- СПИСОК ВСЕХ РЕГИСТРАЦИЙ ----------
@dp.callback_query(F.data == "admin_list")
async def admin_list(callback: types.CallbackQuery):
    """Показывает список всех зарегистрированных игроков"""
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    registrations = db.get_all_registrations()
    
    if not registrations:
        await callback.message.answer(
            "📭 <b>Нет зарегистрированных игроков</b>",
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard()
        )
        await callback.answer()
        return
    
    text = "📋 <b>ВСЕ РЕГИСТРАЦИИ:</b>\n\n"
    
    for i, reg in enumerate(registrations[:10], 1):
        (_, _, username, full_name, _, nickname, reg_date, _, _) = reg
        text += f"<b>{i}.</b> {full_name}\n"
        text += f"   🎭 {nickname}\n"
        text += f"   📅 {reg_date}\n"
        text += f"   🆔 @{username if username else 'нет'}\n"
        text += "━━━━━━━━━━━\n"
    
    text += f"\n<i>Всего: {len(registrations)}</i>"
    
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await callback.answer()

# ---------- ЭКСПОРТ В ФАЙЛ ----------
@dp.message(Command("export"))
@dp.callback_query(F.data == "admin_export")
async def export_registrations(message_or_callback):
    """Экспорт регистраций в текстовый файл"""
    
    if isinstance(message_or_callback, types.CallbackQuery):
        callback = message_or_callback
        message = callback.message
        user_id = callback.from_user.id
        await callback.answer()
    else:
        message = message_or_callback
        user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    registrations = db.get_all_registrations()
    
    if not registrations:
        await message.answer("📭 Нет зарегистрированных игроков")
        return
    
    export_text = f"РЕГИСТРАЦИИ {CLUB_NAME}\n"
    export_text += f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    export_text += "=" * 50 + "\n\n"
    
    for i, reg in enumerate(registrations, 1):
        (_, user_id, username, full_name, birth_date, nickname, reg_date, _, _) = reg
        export_text += f"{i}. {full_name}\n"
        export_text += f"   Ник: {nickname}\n"
        export_text += f"   Дата рождения: {birth_date}\n"
        export_text += f"   Дата регистрации: {reg_date}\n"
        export_text += f"   Telegram: @{username if username else 'нет'}\n"
        export_text += f"   ID: {user_id}\n"
        export_text += "-" * 30 + "\n\n"
    
    filename = f"registrations_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(export_text)
    
    with open(filename, 'rb') as f:
        await message.answer_document(
            types.BufferedInputFile(f.read(), filename=filename),
            caption=f"📊 Экспорт ({len(registrations)} игроков)"
        )
    
    logger.info(f"Admin {message.from_user.id} exported {len(registrations)} registrations")

# ---------- КОМАНДА HELP ----------
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Справка по командам бота"""
    
    help_text = f"""
❓ <b>ПОМОЩЬ ПО БОТУ {CLUB_NAME}</b>

━━━━━━━━━━━━━━━━━━━━━
<b>📌 ОСНОВНЫЕ КОМАНДЫ:</b>

/start - Запустить бота
/help  - Показать справку

━━━━━━━━━━━━━━━━━━━━━
<b>👨‍💼 АДМИН-КОМАНДЫ:</b>

/admin  - Панель администратора
/export - Экспорт списка игроков

━━━━━━━━━━━━━━━━━━━━━
📞 <b>Контакты:</b> {CONTACT_INFO}
    """
    
    await message.answer(
        help_text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# ---------- НЕИЗВЕСТНЫЕ КОМАНДЫ ----------
@dp.message()
async def handle_unknown(message: types.Message):
    """Обработка неизвестных команд"""
    
    await message.answer(
        "❓ <b>Я не понимаю эту команду</b>\n\n"
        "Используйте кнопки меню или /help",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )

# ============ ФЛЕСК ЭНДПОЙНТЫ ============
@app.route('/')
def index():
    """Главная страница - проверка работы"""
    return jsonify({
        "status": "Bot is running!",
        "bot_name": CLUB_NAME,
        "registrations": db.get_registration_count(),
        "admins": len(load_admins()),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    """Health check для Render"""
    return jsonify({"status": "healthy"}), 200

# ============ ИСПРАВЛЕННЫЙ ЗАПУСК БОТА ============
def run_bot_sync():
    """Синхронная обертка для запуска бота в отдельном потоке"""
    import asyncio
    
    # Создаем новый event loop для этого потока
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def start():
        try:
            logger.info("🚀 Бот запускается на Render.com...")
            # Удаляем вебхук перед стартом
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"❌ Ошибка в боте: {e}")
        finally:
            await bot.session.close()
    
    loop.run_until_complete(start())

# ============ ЗАПУСК ============
if __name__ == "__main__":
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot_sync, daemon=True)
    bot_thread.start()
    logger.info("✅ Бот запущен в фоновом потоке")
    
    # Запускаем Flask сервер
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 Flask сервер запущен на порту {port}")
    app.run(host="0.0.0.0", port=port)

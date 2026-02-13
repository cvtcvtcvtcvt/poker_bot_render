"""
ПОКЕРНЫЙ БОТ ДЛЯ RENDER - ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ
С ВАШИМ TELEGRAM ID: 1043425588
"""

import os
import json
import logging
import sqlite3
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, Update

# ============ НАСТРОЙКА ЛОГИРОВАНИЯ ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ FLASK ПРИЛОЖЕНИЕ ============
app = Flask(__name__)

# ============ ТОКЕН И НАСТРОЙКИ ============
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN не найден!")
    exit(1)

# ✅ ВАШ TELEGRAM ID!
SUPER_ADMIN_ID = 1043425588

# ============ НАСТРОЙКИ КЛУБА ============
CLUB_NAME = "SNAP DONK POKER KLUB"
RULES_URL = "https://telegra.ph/Reglament-pokernogo-kluba-SNAP-DONK-01-01"
TOURNAMENT_DATE = "15 марта 2024"
TOURNAMENT_TIME = "19:00"
TOURNAMENT_BUYIN = "2000₽"
TOURNAMENT_LOCATION = "ул. Покерная, д. 1"
CONTACT_INFO = "@club_administrator"

# ============ БАЗА ДАННЫХ ============
class Database:
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
    
    def add_registration(self, user_id, username, full_name, birth_date, nickname):
        reg_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO registrations 
                (user_id, username, full_name, birth_date, nickname, reg_date, agreed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, full_name, birth_date, nickname, reg_date, True))
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
    full_name = State()
    birth_date = State()
    nickname = State()
    agreement = State()
    confirmation = State()

# ============ ИНИЦИАЛИЗАЦИЯ БОТА ============
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============ КЛАВИАТУРЫ ============
def get_start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="📝 РЕГИСТРАЦИЯ",
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
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📜 РЕГЛАМЕНТ",
        url=RULES_URL
    ))
    builder.row(InlineKeyboardButton(
        text="✅ СОГЛАСЕН",
        callback_data="agree"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ ОТМЕНА",
        callback_data="cancel"
    ))
    return builder.as_markup()

def get_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ ПОДТВЕРДИТЬ",
        callback_data="confirm"
    ))
    builder.add(InlineKeyboardButton(
        text="✏️ ЗАНОВО",
        callback_data="register"
    ))
    builder.adjust(1)
    return builder.as_markup()

# ============ ОБРАБОТЧИКИ КОМАНД ============

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome = f"🎰 ДОБРО ПОЖАЛОВАТЬ В {CLUB_NAME}!\n\nВыбери действие:"
    await message.answer(welcome, reply_markup=get_start_keyboard())

@dp.callback_query(F.data == "about")
async def about_club(callback: types.CallbackQuery):
    text = f"""
🏆 {CLUB_NAME}

📅 Турнир: {TOURNAMENT_DATE} {TOURNAMENT_TIME}
💰 Бай-ин: {TOURNAMENT_BUYIN}
📍 {TOURNAMENT_LOCATION}
📞 {CONTACT_INFO}
    """
    await callback.message.answer(text, reply_markup=get_start_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "register")
async def start_registration(callback: types.CallbackQuery, state: FSMContext):
    if db.check_registered(callback.from_user.id):
        await callback.message.answer("⚠️ Вы уже зарегистрированы!")
        await callback.answer()
        return
    
    await callback.message.answer("📝 Введите ваше ФИО:")
    await state.set_state(Registration.full_name)
    await callback.answer()

@dp.message(Registration.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("📅 Введите дату рождения (ДД.ММ.ГГГГ):")
    await state.set_state(Registration.birth_date)

@dp.message(Registration.birth_date)
async def process_birth_date(message: types.Message, state: FSMContext):
    await state.update_data(birth_date=message.text)
    await message.answer("🎭 Введите ваш покерный ник:")
    await state.set_state(Registration.nickname)

@dp.message(Registration.nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer(
        "⚖️ ОЗНАКОМЬТЕСЬ С РЕГЛАМЕНТОМ",
        reply_markup=get_agreement_keyboard()
    )
    await state.set_state(Registration.agreement)

@dp.callback_query(F.data == "agree")
async def process_agreement(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    preview = f"""
✅ Ваши данные:
👤 {data.get('full_name')}
📅 {data.get('birth_date')}
🎭 {data.get('nickname')}

Всё верно?
    """
    await callback.message.answer(preview, reply_markup=get_confirm_keyboard())
    await callback.answer()
    await state.set_state(Registration.confirmation)

@dp.callback_query(F.data == "confirm")
async def confirm_registration(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    success = db.add_registration(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=data.get('full_name'),
        birth_date=data.get('birth_date'),
        nickname=data.get('nickname')
    )
    
    if success:
        await callback.message.answer(
            f"🎉 РЕГИСТРАЦИЯ ЗАВЕРШЕНА!\n\nЖелаем удачи!",
            reply_markup=get_start_keyboard()
        )
        # Уведомление админу (вам!)
        try:
            await bot.send_message(
                SUPER_ADMIN_ID,
                f"✅ Новая регистрация: {data.get('full_name')}"
            )
        except:
            pass
    else:
        await callback.message.answer("❌ Ошибка", reply_markup=get_start_keyboard())
    
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_registration(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Регистрация отменена", reply_markup=get_start_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "my_data")
async def show_my_data(callback: types.CallbackQuery):
    reg = db.get_registration(callback.from_user.id)
    if reg:
        text = f"""
📋 Ваши данные:
👤 {reg[3]}
📅 {reg[4]}
🎭 {reg[5]}
📆 {reg[6]}
        """
    else:
        text = "❌ Вы не зарегистрированы"
    await callback.message.answer(text, reply_markup=get_start_keyboard())
    await callback.answer()

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    count = db.get_registration_count()
    await message.answer(f"🔐 АДМИН-ПАНЕЛЬ\n\nВсего регистраций: {count}")

# ============ WEBHOOK (СИНХРОННАЯ ВЕРСИЯ) ============

WEBHOOK_URL = f"https://poker-bot-render.onrender.com/webhook"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Синхронный обработчик webhook - без ошибок Flask!"""
    try:
        update_data = request.get_json()
        
        # Создаем событийный цикл для асинхронного вызова
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        update = Update.model_validate(update_data, context={"bot": bot})
        loop.run_until_complete(dp.feed_update(bot, update))
        
        return '', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return '', 500

@app.route('/')
def index():
    return jsonify({
        "status": "✅ Bot is running!",
        "bot_name": CLUB_NAME,
        "webhook": WEBHOOK_URL,
        "registrations": db.get_registration_count(),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/set_webhook')
def set_webhook():
    """Устанавливаем вебхук"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def setup():
        await bot.set_webhook(url=WEBHOOK_URL)
        return "✅ Webhook установлен!"
    
    result = loop.run_until_complete(setup())
    return result

# ============ ЗАПУСК ============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Запуск на порту {port}")
    logger.info(f"🌐 Webhook URL: {WEBHOOK_URL}")
    logger.info(f"👑 Админ ID: {SUPER_ADMIN_ID}")
    
    # Устанавливаем вебхук при старте
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.set_webhook(url=WEBHOOK_URL))
    logger.info("✅ Webhook установлен!")
    
    # Запускаем Flask
    app.run(host="0.0.0.0", port=port)

import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
import keyboards as kb

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN environment variable is missing!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

QUIZ_QUESTIONS = [
    {
        "q": "سوال ۱: She ________ English for three years before she moved to London.",
        "options": "A) has studied\nB) had been studying\nC) is studying\nD) studies",
        "correct": "B"
    },
    {
        "q": "سوال ۲: If I ________ enough money, I would travel around the world.",
        "options": "A) had\nB) have\nC) will have\nD) would have",
        "correct": "A"
    },
    {
        "q": "سوال ۳: The project was completed ________ time despite the difficulties.",
        "options": "A) at\nB) on\nC) in\nD) with",
        "correct": "B"
    }
]

class PlacementStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    taking_quiz = State()
    waiting_for_voice = State()

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    await db.add_or_update_user(user.id, user.full_name, user.username or "")
    
    welcome_text = (
        f"سلام {user.first_name} عزیز! 🌟\n"
        f"به **آکادمی زبان آنلاین** خوش آمدید.\n\n"
        f"برای شروع یادگیری و ورود به کلاس‌ها، گزینه‌های زیر در دسترس شماست:"
    )
    await message.answer(welcome_text, reply_markup=kb.main_menu_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "📚 معرفی دوره‌ها و شهریه")
async def show_courses(message: Message):
    courses_info = (
        "🎓 **دوره‌های فعال آکادمی زبان:**\n\n"
        "🔹 **دوره جامع IELTS / TOEFL:**\n"
        "• تکنیک‌های ۴ مهارت + آزمون‌های ماک هفتگی\n"
        "• برگزاری در بستر بیگ‌بلو‌باتن (BigBlueButton)\n\n"
        "🔹 **دوره‌های جنرال و مکالمه (General Speaking):**\n"
        "• از سطح مبتدی تا پیشرفته (A1 - C1)\n"
        "• تمرکز بر روانی کلام و رفع ایرادات گرامری\n\n"
        "🔹 **کلاس‌های خصوصی تک‌نفره و نیمه‌خصوصی:**\n"
        "• برنامه کاملاً منعطف متناسب با تایم زبان‌آموز\n\n"
        "💡 جهت ثبت‌نام، ابتدا تعیین سطح خود را کامل کنید."
    )
    await message.answer(courses_info, parse_mode="Markdown")

@dp.message(F.text == "🎯 آزمون و تعیین سطح آنلاین")
async def start_placement(message: Message, state: FSMContext):
    await message.answer("لطفاً **نام و نام خانوادگی** خود را وارد کنید:")
    await state.set_state(PlacementStates.waiting_for_name)

@dp.message(PlacementStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer(
        "ممنون! لطفاً شماره تماس خود را ارسال کنید تا نتایج برایتان ثبت شود:",
        reply_markup=kb.share_phone_keyboard()
    )
    await state.set_state(PlacementStates.waiting_for_phone)

@dp.message(PlacementStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone, score=0, current_q=0)
    
    user_data = await state.get_data()
    await db.add_or_update_user(
        message.from_user.id,
        user_data['full_name'],
        message.from_user.username or "",
        phone=phone
    )
    
    await message.answer("آزمون تستی شروع شد! 📝\nبه هر سوال با دکمه‌های مربوطه پاسخ دهید.", reply_markup=kb.main_menu_keyboard())
    await send_quiz_question(message, 0)
    await state.set_state(PlacementStates.taking_quiz)

async def send_quiz_question(message: Message, q_idx: int):
    q_data = QUIZ_QUESTIONS[q_idx]
    text = f"{q_data['q']}\n\n{q_data['options']}"
    await message.answer(text, reply_markup=kb.quiz_options_keyboard(q_idx))

@dp.callback_query(F.data.startswith("ans_"))
async def handle_quiz_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_q = data.get("current_q", 0)
    score = data.get("score", 0)
    
    selected_option = callback.data.split("_")[2]
    correct_option = QUIZ_QUESTIONS[current_q]["correct"]
    
    if selected_option == correct_option:
        score += 1
        await state.update_data(score=score)
    
    await callback.answer("پاسخ شما ثبت شد.")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    next_q = current_q + 1
    if next_q < len(QUIZ_QUESTIONS):
        await state.update_data(current_q=next_q)
        await send_quiz_question(callback.message, next_q)
    else:
        await callback.message.answer(
            f"✅ آزمون تستی به پایان رسید. نمره تستی شما: {score} از {len(QUIZ_QUESTIONS)}\n\n"
            "🎙 **مرحله دوم (ارزیابی اسپیکینگ):**\n"
            "لطفاً یک ویس حدود ۳۰ تا ۶۰ ثانیه‌ای به انگلیسی ضبط کنید و به این سوال پاسخ دهید:\n"
            "_\"Tell us about your background, hobbies, and why you want to learn English.\"_\n\n"
            "(اگر مایل نیستید، دکمه منو را بزنید).",
            parse_mode="Markdown"
        )
        await state.set_state(PlacementStates.waiting_for_voice)

@dp.message(PlacementStates.waiting_for_voice, F.voice)
async def process_voice(message: Message, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    voice_id = message.voice.file_id
    
    await db.save_placement_result(message.from_user.id, score, voice_id)
    
    await message.answer(
        "🎉 عالی بود! نتیجه آزمون و نمونه صدای شما برای سوپروایزر ارسال شد.\n"
        "به زودی جهت مشاوره و تعیین سطح نهایی با شما تماس گرفته می‌شود.",
        reply_markup=kb.main_menu_keyboard()
    )
    
    if ADMIN_ID:
        try:
            admin_msg = (
                f"📥 **لید جدید تعیین سطح!**\n"
                f"👤 نام: {data.get('full_name')}\n"
                f"📱 شماره تماس: {data.get('phone')}\n"
                f"📊 نمره کوئیز: {score} / {len(QUIZ_QUESTIONS)}\n"
                f"🆔 یوزرنیم: @{message.from_user.username or 'ندارد'}"
            )
            await bot.send_message(chat_id=int(ADMIN_ID), text=admin_msg, parse_mode="Markdown")
            await bot.send_voice(chat_id=int(ADMIN_ID), voice=voice_id, caption="🎙 نمونه صدای زبان‌آموز")
        except Exception as e:
            logging.error(f"Error sending to admin: {e}")
            
    await state.clear()

@dp.message(F.text == "📞 ارتباط با پشتیبانی و مشاوره")
async def support_info(message: Message):
    await message.answer(
        "👩‍🏫 **پشتیبانی و مشاوره آموزشی آکادمی:**\n\n"
        "جهت هماهنگی زمان مصاحبه یا پاسخ به سوالات می‌توانید با آیدی پشتیبانی در ارتباط باشید:\n"
        "👉 @Zingo_Support"
    )

async def main():
    await db.init_db()
    logging.info("Database initialized successfully.")
    logging.info("Bot is starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

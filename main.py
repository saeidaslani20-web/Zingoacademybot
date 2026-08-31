import os
import sys
import logging
import asyncio
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ایمپورت ماژول‌های داخلی پروژه
import database as db
import keyboards as kb
from questions import QUESTIONS, calculate_cefr_level

# تنظیمات لاگینگ
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# دریافت متغیرهای محیطی
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "53776390")

if not BOT_TOKEN:
    logging.error("BOT_TOKEN is not set in environment variables!")
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    ADMIN_ID = 53776390

# ثابت‌های پشتیبانی
SUPPORT_PHONE = "00989104446166"
SUPPORT_ID = "@Zingo_ielts"
SUPPORT_TEXT = f"\n\n📞 **پشتیبانی آکادمی زینگو:**\nتلفن: `{SUPPORT_PHONE}`\nآیدی تلگرام: {SUPPORT_ID}"

# مقداردهی اولیه Bot و Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- وضعیت‌های ماشین حالت (FSM States) ---
class AuthStates(StatesGroup):
    waiting_for_role = State()
    entering_name = State()
    waiting_for_phone = State()

class QuizStates(StatesGroup):
    answering = State()

class VoiceStates(StatesGroup):
    waiting_for_voice = State()

class ReceiptStates(StatesGroup):
    waiting_for_receipt = State()

class WritingStates(StatesGroup):
    waiting_for_receipt = State()
    waiting_for_file = State()

class TeacherStates(StatesGroup):
    waiting_for_resume = State()
    waiting_for_demo = State()


# --- توابع اعتبارسنجی ---
def is_persian_name(text: str) -> bool:
    return bool(re.match(r"^[\u0600-\u06FF\s]+$", text.strip()))

def is_valid_phone(text: str) -> bool:
    cleaned = text.replace("+", "").replace(" ", "")
    return bool(re.match(r"^(09\d{9}|989\d{9})$", cleaned))


# --- هندلرهای شروع و ثبت‌نام (/start) ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = db.get_user(message.from_user.id)
    if user:
        role = user.get("role", "student")
        if role == "teacher":
            await message.answer("سلام استاد گرامی! به پنل مدرسین آکادمی زینگو خوش آمدید.", reply_markup=kb.teacher_main_menu())
        else:
            await message.answer("سلام! به آکادمی زبان زینگو خوش آمدید. لطفاً گزینه مورد نظر خود را انتخاب کنید:", reply_markup=kb.student_main_menu())
    else:
        await state.set_state(AuthStates.waiting_for_role)
        await message.answer("سلام! به بات آکادمی زبان زینگو خوش آمدید 🌟\nلطفاً نقش خود را انتخاب کنید:", reply_markup=kb.role_selection_keyboard())

@dp.message(AuthStates.waiting_for_role, F.text.in_(["🎓 زبان‌آموز", "👨‍🏫 متقاضی تدریس / استاد"]))
async def process_role_selection(message: types.Message, state: FSMContext):
    role = "student" if "زبان‌آموز" in message.text else "teacher"
    await state.update_data(role=role)
    await state.set_state(AuthStates.entering_name)
    await message.answer("لطفاً نام و نام خانوادگی خود را **فقط به زبان فارسی** وارد کنید:", reply_markup=types.ReplyKeyboardRemove())

@dp.message(AuthStates.entering_name, F.text)
async def process_name_input(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not is_persian_name(name):
        await message.answer("⚠️ لطفاً نام خود را فقط با حروف فارسی وارد کنید:")
        return
    
    await state.update_data(full_name=name)
    await state.set_state(AuthStates.waiting_for_phone)
    await message.answer("📱 لطفاً شماره تماس خود را ارسال کنید یا دکمه زیر را لمس کنید:", reply_markup=kb.phone_request_keyboard())

@dp.message(AuthStates.waiting_for_phone, F.text | F.contact)
async def process_phone_input(message: types.Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
    
    if not is_valid_phone(phone):
        await message.answer("⚠️ شماره تماس نامعتبر است. لطفاً شماره معتبر ۱۱ رقمی (مانند ۰۹۱۲۳۴۵۶۷۸۹) وارد کنید:")
        return
    
    data = await state.get_data()
    role = data.get("role", "student")
    full_name = data.get("full_name")
    
    db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=full_name,
        phone=phone,
        role=role
    )
    await state.clear()
    
    if role == "teacher":
        await message.answer(f"✅ ثبت‌نام شما با موفقیت تکمیل شد همکار گرامی {full_name}!", reply_markup=kb.teacher_main_menu())
    else:
        await message.answer(f"✅ ثبت‌نام شما با موفقیت تکمیل شد {full_name} عزیز!", reply_markup=kb.student_main_menu())


# --- هندلر تعیین سطح آنلاین ---
@dp.message(F.text == "📝 تعیین سطح آنلاین (۴۰ سوال)")
async def start_quiz(message: types.Message, state: FSMContext):
    await state.set_state(QuizStates.answering)
    await state.update_data(current_q=0, score=0, answers=[])
    
    first_q = QUESTIONS[0]
    await message.answer(
        f"📝 **سوال ۱ از ۴۰**:\n\n{first_q['question']}",
        reply_markup=kb.question_keyboard(first_q['options'], 0),
        parse_mode="Markdown"
    )

@dp.callback_query(QuizStates.answering, F.data.startswith("ans_"))
async def handle_quiz_answer(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_q = data.get("current_q", 0)
    score = data.get("score", 0)
    
    selected_option = int(callback.data.split("_")[1])
    correct_option = QUESTIONS[current_q]["correct"]
    
    if selected_option == correct_option:
        score += 1
    
    next_q = current_q + 1
    if next_q < len(QUESTIONS):
        await state.update_data(current_q=next_q, score=score)
        q_data = QUESTIONS[next_q]
        await callback.message.edit_text(
            f"📝 **سوال {next_q + 1} از ۴۰**:\n\n{q_data['question']}",
            reply_markup=kb.question_keyboard(q_data['options'], next_q),
            parse_mode="Markdown"
        )
    else:
        # اتمام آزمون
        result = calculate_cefr_level(score)
        user_info = db.get_user(callback.from_user.id)
        user_name = user_info.get("full_name", callback.from_user.full_name) if user_info else callback.from_user.full_name
        phone = user_info.get("phone", "ثبت نشده") if user_info else "ثبت نشده"
        
        report_user = (
            f"🏁 **نتیجه نهایی آزمون تعیین سطح**\n\n"
            f"👤 نام: {user_name}\n"
            f"📊 نمره: {score} از ۴۰\n"
            f"🎯 سطح تعیین‌شده: **{result['level']}**\n"
            f"💡 دوره پیشنهادی: **{result['course']}**"
            f"{SUPPORT_TEXT}"
        )
        await callback.message.edit_text(report_user, parse_mode="Markdown")
        
        # ارسال گزارش به ادمین
        admin_report = (
            f"📊 **نتیجه آزمون تعیین سطح جدید**\n\n"
            f"👤 کاربر: {user_name}\n"
            f"📱 تلفن: `{phone}`\n"
            f"🆔 آیدی عددی: `{callback.from_user.id}`\n"
            f"🔗 یوزرنیم: @{callback.from_user.username or 'ندارد'}\n"
            f"📈 نمره: {score}/40\n"
            f"🎯 سطح: {result['level']}\n"
            f"📚 پیشنهاد: {result['course']}"
        )
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_report, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send quiz report to admin: {e}")
        
        await state.clear()
    await callback.answer()


# --- هندلر ویس اسپیکینگ ---
@dp.message(F.text == "🎙 ارسال ویس اسپیکینگ")
async def ask_for_voice(message: types.Message, state: FSMContext):
    await state.set_state(VoiceStates.waiting_for_voice)
    await message.answer(
        "🎙 لطفاً یک فایل صوتی (ویس) ۱ الی ۲ دقیقه‌ای به زبان انگلیسی شامل معرفی خود، علایق و اهدافتان ارسال فرمایید:"
    )

@dp.message(VoiceStates.waiting_for_voice, F.voice | F.audio)
async def process_voice(message: types.Message, state: FSMContext):
    user_info = db.get_user(message.from_user.id)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ندارد") if user_info else "ندارد"
    
    caption = (
        f"🎙 **ویس ارسالی جهت تعیین سطح اسپیکینگ**\n"
        f"👤 کاربر: {user_name}\n"
        f"📱 شماره: `{phone}`\n"
        f"🆔 آیدی عددی: `{message.from_user.id}`\n"
        f"🔗 یوزرنیم: @{message.from_user.username or 'ندارد'}"
    )
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    try:
        await bot.send_voice(chat_id=ADMIN_ID, voice=file_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error forwarding voice to admin: {e}")
    
    await message.answer(f"✅ ویس شما با موفقیت ارسال شد و توسط اساتید آکادمی بررسی خواهد شد.{SUPPORT_TEXT}")
    await state.clear()


# --- هندلر فیش واریزی ---
@dp.message(F.text == "💳 ارسال فیش واریزی")
async def ask_for_receipt(message: types.Message, state: FSMContext):
    await state.set_state(ReceiptStates.waiting_for_receipt)
    await message.answer("💳 لطفاً تصویر واضح فیش واریزی خود را ارسال کنید:")

@dp.message(ReceiptStates.waiting_for_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    user_info = db.get_user(message.from_user.id)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ندارد") if user_info else "ندارد"
    
    photo_id = message.photo[-1].file_id
    db.add_receipt(message.from_user.id, photo_id)
    
    caption = (
        f"💳 **فیش واریزی جدید**\n"
        f"👤 نام: {user_name}\n"
        f"📱 تلفن: `{phone}`\n"
        f"🆔 آیدی: `{message.from_user.id}`\n"
        f"🔗 یوزرنیم: @{message.from_user.username or 'ندارد'}"
    )
    try:
        await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error forwarding receipt to admin: {e}")
    
    await message.answer(f"✅ فیش واریزی شما با موفقیت ثبت شد و در اسرع وقت تأیید می‌گردد.{SUPPORT_TEXT}")
    await state.clear()


# --- هندلر دوره‌ها و سرویس رایتینگ ---
@dp.message(F.text == "📚 مشاهده دوره‌ها و تصحیح رایتینگ")
async def show_courses(message: types.Message):
    await message.answer(
        "📚 **دوره‌های آموزشی و خدمات تخصصی آکادمی زینگو:**\nلطفاً گزینه مورد نظر خود را انتخاب فرمایید:",
        reply_markup=kb.courses_inline_keyboard()
    )

@dp.callback_query(F.data == "c_writing")
async def start_writing_service(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(WritingStates.waiting_for_receipt)
    await callback.message.answer("✍️ **سرویس تصحیح تخصصی رایتینگ**\n\nلطفاً ابتدا تصویر فیش واریزی خود را ارسال کنید:")
    await callback.answer()

@dp.message(WritingStates.waiting_for_receipt, F.photo)
async def process_writing_receipt(message: types.Message, state: FSMContext):
    await state.update_data(receipt_photo_id=message.photo[-1].file_id)
    await state.set_state(WritingStates.waiting_for_file)
    await message.answer("✅ فیش دریافت شد.\nحالا لطفاً فایل رایتینگ خود را به صورت فایل (PDF یا Word) ارسال کنید:")

@dp.message(WritingStates.waiting_for_file, F.document)
async def process_writing_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    receipt_photo_id = data.get("receipt_photo_id")
    file_id = message.document.file_id
    file_name = message.document.file_name or "Writing_File"
    
    user_info = db.get_user(message.from_user.id)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ندارد") if user_info else "ندارد"
    
    admin_caption = (
        f"✍️ **درخواست جدید تصحیح رایتینگ**\n"
        f"👤 کاربر: {user_name}\n"
        f"📱 تلفن: `{phone}`\n"
        f"🆔 آیدی عددی: `{message.from_user.id}`\n"
        f"📄 فایل: {file_name}"
    )
    
    try:
        await bot.send_photo(chat_id=ADMIN_ID, photo=receipt_photo_id, caption=admin_caption, parse_mode="Markdown")
        await bot.send_document(chat_id=ADMIN_ID, document=file_id, caption=f"📄 فایل رایتینگ {user_name}")
    except Exception as e:
        logging.error(f"Error sending writing package to admin: {e}")
        
    await message.answer(f"✅ فیش و فایل رایتینگ شما با موفقیت برای تیم آموزشی ارسال شد. نتیجه تصحیح تا ۴۸ ساعت آینده برای شما ارسال خواهد شد.{SUPPORT_TEXT}")
    await state.clear()

@dp.callback_query(F.data.in_(["c_ttc", "c_ielts", "c_speak", "back"]))
async def handle_course_details(callback: types.CallbackQuery):
    if callback.data == "c_ttc":
        msg = "🎓 **دوره تربیت مدرس TTC:**\nبرگزاری به صورت آنلاین در محیط BigBlueButton، کارگاه‌های عملی و اعطای گواهی معتبر."
    elif callback.data == "c_ielts":
        msg = "🚀 **دوره‌های تخصصی IELTS / TOEFL:**\nتمرکز بر مهارت‌های ۴‌گانه، رفع اشکال فردی و تحلیل متدهای نمره‌آوری."
    elif callback.data == "c_speak":
        msg = "🗣 **دوره‌های مکالمه Speak Now:**\nتقویت روان‌صحبت‌کردن و اعتماد به نفس به صورت خصوصی و نیمه‌گروهی."
    else:
        await callback.message.delete()
        await callback.answer()
        return

    await callback.message.answer(f"{msg}{SUPPORT_TEXT}")
    await callback.answer()


# --- هندلر پشتیبانی ---
@dp.message(F.text == "📞 پشتیبانی و مشاوره")
async def show_support(message: types.Message):
    await message.answer(
        f"📞 **ارتباط با واحد آموزش و پشتیبانی آکادمی زینگو:**\n\n"
        f"📱 تماس مستقیم: `{SUPPORT_PHONE}`\n"
        f"💬 تلگرام: {SUPPORT_ID}\n\n"
        f"ساعات پاسخگویی: همه‌روزه از ۹ الی ۲۱"
    )


# --- بخش مدرسین (همکاری با ما) ---
@dp.message(F.text == "📄 ارسال رزومه و مدارک")
async def teacher_resume_start(message: types.Message, state: FSMContext):
    await state.set_state(TeacherStates.waiting_for_resume)
    await message.answer("لطفاً فایل رزومه (CV) خود را به صورت PDF ارسال کنید:")

@dp.message(TeacherStates.waiting_for_resume, F.document)
async def teacher_resume_received(message: types.Message, state: FSMContext):
    await state.update_data(resume_id=message.document.file_id)
    await state.set_state(TeacherStates.waiting_for_demo)
    await message.answer("✅ رزومه دریافت شد. حالا لطفاً یک نمونه تدریس یا ویس معرفی (Demo) ارسال بفرمایید:")

@dp.message(TeacherStates.waiting_for_demo, F.voice | F.audio | F.video | F.document)
async def teacher_demo_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    resume_id = data.get("resume_id")
    demo_id = message.voice.file_id if message.voice else (message.audio.file_id if message.audio else message.document.file_id)
    
    user_info = db.get_user(message.from_user.id)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ندارد") if user_info else "ندارد"
    
    admin_caption = (
        f"👨‍🏫 **درخواست همکاری جدید مدرس**\n"
        f"👤 نام: {user_name}\n"
        f"📱 تلفن: `{phone}`\n"
        f"🆔 آیدی: `{message.from_user.id}`"
    )
    
    try:
        await bot.send_document(chat_id=ADMIN_ID, document=resume_id, caption=admin_caption)
        await bot.send_voice(chat_id=ADMIN_ID, voice=demo_id, caption=f"🎙 نمونه تدریس {user_name}")
    except Exception as e:
        logging.error(f"Error forwarding teacher application: {e}")
        
    await message.answer(f"✅ مدارک و نمونه تدریس شما با موفقیت ثبت شد. مدیریت آموزشی پس از بررسی با شما تماس خواهند گرفت.{SUPPORT_TEXT}")
    await state.clear()


# --- تابع اصلی استارت بات ---
async def main():
    db.init_db()
    logging.info("Database initialized successfully.")
    logging.info("Starting bot polling...")
    # حذف وب‌هوک‌های قبلی در صورت وجود
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

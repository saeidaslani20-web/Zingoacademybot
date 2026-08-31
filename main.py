import os
import sys
import logging
import asyncio
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
import keyboards as kb
from questions import QUESTIONS, calculate_cefr_level

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "53776390")

if not BOT_TOKEN:
    logging.error("BOT_TOKEN is not set in environment variables!")
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    ADMIN_ID = 53776390

SUPPORT_PHONE = "00989104446166"
SUPPORT_ID = "@Zingo_ielts"
SUPPORT_FOOTER = f"\n\n📞 **پشتیبانی آکادمی زینگو:**\n📱 تلفن: `{SUPPORT_PHONE}`\n💬 تلگرام: {SUPPORT_ID}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- وضعیت‌های FSM ---
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


# --- اعتبارسنجی‌ها ---
def is_persian_name(text: str) -> bool:
    return bool(re.match(r"^[\u0600-\u06FF\s]+$", text.strip()))

def is_valid_phone(text: str) -> bool:
    cleaned = text.replace("+", "").replace(" ", "")
    return bool(re.match(r"^(09\d{9}|989\d{9})$", cleaned))


# --- استارت ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = db.get_user(message.from_user.id)
    if user:
        role = user.get("role", "student")
        if role == "teacher":
            await message.answer("سلام استاد گرامی! به پنل مدرسین آکادمی زینگو خوش آمدید.", reply_markup=kb.teacher_main_menu())
        else:
            await message.answer("سلام! به آکادمی زبان زینگو خوش آمدید 🌟\nلطفاً گزینه مورد نظر خود را انتخاب کنید:", reply_markup=kb.student_main_menu())
    else:
        await state.set_state(AuthStates.waiting_for_role)
        await message.answer("سلام! به بات آکادمی زبان زینگو خوش آمدید 🌟\nلطفاً نقش خود را انتخاب کنید:", reply_markup=kb.role_selection_keyboard())


# --- ثبت نام ---
@dp.message(AuthStates.waiting_for_role, F.text.in_(["🎓 زبان‌آموز", "👨‍🏫 متقاضی تدریس / استاد"]))
async def process_role_selection(message: types.Message, state: FSMContext):
    role = "student" if "زبان‌آموز" in message.text else "teacher"
    await state.update_data(role=role)
    await state.set_state(AuthStates.entering_name)
    await message.answer("لطفاً نام و نام خانوادگی خود را **فقط به فارسی** وارد کنید:", reply_markup=types.ReplyKeyboardRemove())

@dp.message(AuthStates.entering_name, F.text)
async def process_name_input(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not is_persian_name(name):
        await message.answer("⚠️ لطفاً نام و نام خانوادگی خود را فقط با حروف فارسی وارد کنید:")
        return
    
    await state.update_data(full_name=name)
    await state.set_state(AuthStates.waiting_for_phone)
    await message.answer("📱 لطفاً شماره تماس خود را ارسال کنید یا دکمه زیر را بزنید:", reply_markup=kb.phone_request_keyboard())

@dp.message(AuthStates.waiting_for_phone, F.text | F.contact)
async def process_phone_input(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text.strip()
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
        await message.answer(f"✅ همکار گرامی {full_name}، ثبت‌نام شما کامل شد.", reply_markup=kb.teacher_main_menu())
    else:
        await message.answer(f"✅ {full_name} عزیز، ثبت‌نام شما کامل شد. از منوی زیر استفاده فرمایید:", reply_markup=kb.student_main_menu())


# --- دوره‌ها ---
@dp.message(F.text == "📚 مشاهده دوره‌ها و تصحیح رایتینگ")
async def show_courses_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📚 **لیست دوره‌های تخصصی و خدمات آکادمی زینگو:**\n\nبرای مشاهده جزئیات هر دوره یا درخواست تصحیح رایتینگ، روی گزینه مورد نظر کلیک کنید:",
        reply_markup=kb.courses_inline_keyboard()
    )

@dp.callback_query(F.data == "c_ttc")
async def course_ttc_info(callback: types.CallbackQuery):
    text = (
        "🎓 **دوره جامع تربیت مدرس (TTC)**\n\n"
        "▫️ مناسب برای علاقه‌مندان به تدریس زبان انگلیسی\n"
        "▫️ آموزش متدهای نوین تدریس (CLT, TBLT)\n"
        "▫️ برگزاری آنلاین در بستر BigBlueButton با کارگاه‌های عملی (Teaching Practice)\n"
        "▫️ اعطای مدرک معتبر در پایان دوره"
        f"{SUPPORT_FOOTER}"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "c_ielts")
async def course_ielts_info(callback: types.CallbackQuery):
    text = (
        "🚀 **دوره‌های آمادگی آزمون IELTS / TOEFL**\n\n"
        "▫️ تحلیل دقیق تکنیک‌های هر ۴ مهارت (Listening, Reading, Writing, Speaking)\n"
        "▫️ برنامه‌ریزی اختصاصی متناسب با نمره هدف (6.5 تا +8)\n"
        "▫️ شبیه‌سازی تست‌های استاندارد کمبریج و بررسی نقاط ضعف"
        f"{SUPPORT_FOOTER}"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "c_speak")
async def course_speak_info(callback: types.CallbackQuery):
    text = (
        "🗣 **دوره‌های مکالمه روان (Speak Now)**\n\n"
        "▫️ افزایش چشمگیر دامنه لغات کاربردی و روانی کلام (Fluency)\n"
        "▫️ رفع موانع ذهنی و استرس مکالمه با موضوعات روزمره و کاری\n"
        "▫️ کلاس‌های خصوصی و نیمه‌گروهی متناسب با تایم شما"
        f"{SUPPORT_FOOTER}"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "close_menu")
async def close_menu_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()


# --- تصحیح رایتینگ ---
@dp.callback_query(F.data == "c_writing")
async def start_writing_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(WritingStates.waiting_for_receipt)
    msg = (
        "✍️ **سرویس تحلیل و تصحیح تخصصی رایتینگ (IELTS / TOEFL)**\n\n"
        "این سرویس شامل تصحیح گرامر، لغت، ساختار استدلال و نمره‌دهی تفکیکی بر اساس معیارهای استاندارد است.\n\n"
        "💳 **مرحله اول:** لطفاً ابتدا تصویر **فیش واریزی** خود را ارسال فرمایید:"
    )
    await callback.message.answer(msg, parse_mode="Markdown")
    await callback.answer()

@dp.message(WritingStates.waiting_for_receipt, F.photo)
async def writing_receipt_received(message: types.Message, state: FSMContext):
    await state.update_data(writing_receipt=message.photo[-1].file_id)
    await state.set_state(WritingStates.waiting_for_file)
    await message.answer("✅ فیش واریزی دریافت شد.\n\n📄 **مرحله دوم:** حالا لطفاً فایل رایتینگ خود را به صورت سند (فایل Word یا PDF) ارسال فرمایید:")

@dp.message(WritingStates.waiting_for_file, F.document)
async def writing_file_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    receipt_id = data.get("writing_receipt")
    doc_id = message.document.file_id
    doc_name = message.document.file_name or "Writing_Document"
    
    user_info = db.get_user(message.from_user.id)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ثبت نشده") if user_info else "ثبت نشده"
    
    admin_caption = (
        f"✍️ **درخواست جدید تصحیح رایتینگ**\n\n"
        f"👤 نام: {user_namecallback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(WritingStates.waiting_for_receipt)
    msg = (
        "✍️ **سرویس تحلیل و تصحیح تخصصی رایتینگ (IELTS / TOEFL)**\n\n"
        "این سرویس شامل تصحیح گرامر، لغت، ساختار استدلال و نمره‌دهی تفکیکی بر اساس معیارهای استاندارد است.\n\n"
        "💳 **مرحله اول:** لطفاً ابتدا تصویر **فیش واریزی** خود را ارسال فرمایید:"
    )
    await callback.message.answer(msg, parse_mode="Markdown")
    await callback.answer()

@dp.message(WritingStates.waiting_for_receipt, F.photo)
async def writing_receipt_received(message: types.Message, state: FSMContext):
    await state.update_data(writing_receipt=message.photo[-1].file_id)
    await state.set_state(WritingStates.waiting_for_file)
    await message.answer("✅ فیش واریزی دریافت شد.\n\n📄 **مرحله دوم:** حالا لطفاً فایل رایتینگ خود را به صورت سند (فایل Word یا PDF) ارسال فرمایید:")

@dp.message(WritingStates.waiting_for_file, F.document)
async def writing_file_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    receipt_id = data.get("writing_receipt")
    doc_id = message.document.file_id
    doc_name = message.document.file_name or "Writing_Document"
    
    user_info = db.get_user(message.from_user.id)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ثبت نشده") if user_info else "ثبت نشده"
    
    admin_caption = (
        f"✍️ **درخواست جدید تصحیح رایتینگ**\n\n"
        f"👤 نام: {user_namedata.split("_")[1])
    correct_option = QUESTIONS[current_q]["correct"]
    
    if selected_option == correct_option:
        score += 1
    
    next_q = current_q + 1
    if next_q < len(QUESTIONS):
        await state.update_data(current_q=next_q, score=score)
        q_data = QUESTIONS[next_q]
        await callback.message.edit_text(
            f"📝 **سوال {next_q + 1} از {len(QUESTIONS)}**:\n\n{q_data['question']}",
            reply_markup=kb.question_keyboard(q_data['options'], next_q),
            parse_mode="Markdown"
        )
    else:
        result = calculate_cefr_level(score)
        user_info = db.get_user(callback.from_user.id)
        user_name = user_info.get("full_name", callback.from_user.full_name) if user_info else callback.from_user.full_name
        phone = user_info.get("phone", "ثبت نشده") if user_info else "ثبت نشده"
        
        user_report = (
            f"🏁 **نتیجه نهایی آزمون تعیین سطح**\n\n"
            f"👤 کاربر گرامی: **{user_name}**\n"
            f"📊 نمره شما: **{score} از {len(QUESTIONS)}**\n"
            f"🎯 سطح تخمینی شما: **{result['level']}**\n"
            f"💡 دوره پیشنهادی آکادمی: **{result['course']}**"
            f"{SUPPORT_FOOTER}"
        )
        await callback.message.edit_text(user_report, parse_mode="Markdown")
        
        admin_report = (
            f"📊 **نتیجه آزمون تعیین سطح جدید**\n\n"
            f"👤 نام: {user_name}\n"
            f"📱 تلفن: `{phone}`\n"
            f"🆔 آیدی عددی: `{callback.from_user.id}`\n"
            f"🔗 یوزرنیم: @{callback.from_user.username or 'ندارد'}\n"
            f"📈 نمره: {score}/{len(QUESTIONS)}\n"
            f"🎯 سطح: {result['level']}\n"
            f"📚 دوره پیشنهادی: {result['course']}"
        )
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_report, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Error sending quiz result to admin: {e}")
            
        await state.clear()
    await callback.answer()


# --- ویس اسپیکینگ ---
@dp.message(F.text == "🎙 ارسال ویس اسپیکینگ")
async def voice_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.setوتی (ویس) ۱ الی ۲ دقیقه‌ای به زبان انگلیسی شامل معرفی، اهداف یادگیری و موضوع دلخواه خود ارسال بفرمایید:"
    )

@dp.message(VoiceStates.waiting_for_voice, F.voice | F.audio بفرمایید:"
    )

@dp.message(VoiceStates.waiting_for_voice, F.voice | F.audio)
async def voice_received(message: types.Message, state: FSMContext):
    user_info = db.get_user(message.from_user.id)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ثبت نشده") if user_info else "ثبت نشده"
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    caption = (
        f"🎙 **ویس ارسالی تعیین سطح اسپیکینگ**\n\n"
        f"👤 کاربر: {user_name}\n"
        f"📱 تلفن: `{phone}`\n"
        f"🆔 آیدی عددی: `{message.from_user.id}`\n"
        f"🔗 یوزرنیم: @{message.from_user.username or 'ندارد'}"
    )
    
    try:
        await bot.send_voice(chat_id=ADMIN_ID, voice=file_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error sending voice to admin: {e}")
        
    await message.answer(f"✅ ویس شما با موفقیت ارسال شد و توسط اساتید بررسی می‌گردد.{SUPPORT_FOOTER}")
    await state.clear()


# --- فیش واریزی ---
@dp.message(F.text == "💳 ارسال فیش واریزی")
async def receipt_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(ReceiptStates.waiting_for_receipt)
    await message.answer("💳 لطفاً تصویر واضح فیش واریزی خود را ارسال فرمایید:")

@dp.message(ReceiptStates.waiting_for_receipt, F.photo)
async def receipt_received(message: types.Messagephone", "ثبت نشده") if user_info else "ثبت نشده"
    
    photo_id = message.photoid)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ثبت نشده") if user_info else "ثبت نشده"
    
    photo_id = message.photo[-1].file_id
    db.add_receipt(message.from_user.id, photo_id)
    
    caption = (
        f"💳 **فیش واریزی جدید**\n\n"
        f"👤 کاربر: {user_name}\n"
        f"📱 تلفن: `{phone}`\n"
        f"🆔 آیدی عددی: `{message.from_user.id}`\n"
        f"🔗 یوزرنیم: @{message.from_user.username or 'ندارد'}"
    )
    try:
        await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error forwarding receipt: {e}")
        
    await message.answer(f"✅ فیش واریزی شما با موفقیت ثبت گردید.{SUPPORT_FOOTER}")
    await state.clear()


# --- پشتیبانی ---
@dp.message(F.text == "📞 پشتیبانی و مشاوره")
async def support_info(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"📞 **واحد مشاوره و ثبت‌نام آکادمی زبان زینگو:**\n\n"
        f"📱 تلفن مستقیم: `{SUPPORT_PHONE}`\n"
        f"💬 ارتباط در تلگرام: {SUPPORT_ID}\n\n"
        f"ساعات پاسخگویی: همه‌روزه از ساعت ۹:۰۰ الی ۲۱:۰۰"
    )


# --- بخش مدرسین ---
@dp.message(F.text == "📄 ارسال رزومه و مدارک")
async def teacher_resume_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(TeacherStates.waiting_for_resume)
    await message.answer("لطفاً فایل رزومه (CV) خود را به صورت PDF ارسال کنید:")

@dp.message(TeacherStates.waiting_for_resume, F.document)
async def teacher_resume_received(message: types.Message, state: FSMContext):
    await state.update_data(resume_id=message.document.file_id)
    await state.set_state(TeacherStates.waiting_for_demo)
    await message.answer("✅ رزومه دریافت شد. حالا لطفاً یک نمونه تدریس کوتاه یا ویس معرفی (Demo) ارسال فرمایید:")

@dp.message(TeacherStates.waiting_for_demo, F.voice | F.audio | F.video | F.document)
async def teacher_demo_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    resume_id = data.get("resume_id")
    demo_id = message.voice.file_id if message.voice else (message.audio.file_id if message.audio else message.document.file_id)
    
    user_info = db.get_user(message.from_user.id)
    user_name = user_info.get("full_name", message.from_user.full_name) if user_info else message.from_user.full_name
    phone = user_info.get("phone", "ثبت نشده") if user_info else "ثبت نشده"
    
    admin_caption = (
        f"👨‍🏫 **رزومه متقاضی تدریس جدید**\n\n"
        f"👤 نام: {user_name}\n"
        f"📱 تلفن: `{phone}`\n"
        f"🆔 آیدی: `{message.from_user.id}`"
    )
    
    try:
        await bot.send_document(chat_id=ADMIN_ID, document=resume_id, caption=admin_caption)
        await bot.send_voice(chat_id=ADMIN_ID, voice=demo_id, caption=f"🎙 نمونه تدریس {user_name}")
    except Exception as e:
        logging.error(f"Error forwarding teacher application: {e}")
        
    await message.answer(f"✅ مدارک و نمونه تدریس شما با موفقیت ثبت شد. مدیریت آموزشی آکادمی با شما تماس خواهند گرفت.{SUPPORT_FOOTER}")
    await state.clear()


# --- راه‌اندازی ربات ---
async def main():
    db.init_db()
    logging.info("Database initialized successfully.")
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

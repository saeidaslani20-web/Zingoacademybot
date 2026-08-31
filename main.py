# main.py
import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import init_db, get_user, save_user, save_placement_result, save_receipt, save_teacher_application
from keyboards import (
    role_selection_keyboard,
    phone_request_keyboard,
    student_main_menu,
    teacher_main_menu,
    courses_inline_keyboard,
    question_keyboard
)
from questions import QUESTIONS, calculate_cefr_level

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "53776390"))
SUPPORT_PHONE = "00989104446166"
SUPPORT_ID = "@Zingo_ielts"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- ماشین‌های حالت (FSM States) ---
class AuthStates(StatesGroup):
    choosing_role = State()
    entering_name = State()
    waiting_for_phone = State()

class PlacementStates(StatesGroup):
    answering = State()

class VoiceStates(StatesGroup):
    waiting_for_voice = State()

class ReceiptStates(StatesGroup):
    waiting_for_course = State()
    waiting_for_receipt = State()

class TeacherStates(StatesGroup):
    waiting_for_info = State()
    waiting_for_resume = State()
    waiting_for_demo = State()

# --- شروع و احراز هویت هوشمند ---
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if user:
        role = user[1]
        name = user[2]
        if role == "teacher":
            await message.answer(f"سلام استاد {name} گرامی! 👨‍🏫\nبه پنل همکاران آکادمی زینگو خوش آمدید.", reply_markup=teacher_main_menu())
        else:
            await message.answer(f"سلام {name} عزیز! 🌟\nبه پنل زبان‌آموزان آکادمی زینگو خوش آمدید.", reply_markup=student_main_menu())
        return

    await state.set_state(AuthStates.choosing_role)
    await message.answer(
        "👋 **به آکادمی زبان بین‌المللی زینگو (Zingo) خوش آمدید.**\n\n"
        "لطفاً برای شروع و دریافت دسترسی اختصاصی، نقش خود را انتخاب کنید:",
        reply_markup=role_selection_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(AuthStates.choosing_role, F.text.in_(["🎓 من زبان‌آموز هستم", "👨‍🏫 من مدرس / متقاضی تدریس هستم"]))
async def process_role_choice(message: types.Message, state: FSMContext):
    role = "student" if "زبان‌آموز" in message.text else "teacher"
    await state.update_data(role=role)
    await state.set_state(AuthStates.entering_name)
    await message.answer("لطفاً **نام و نام خانوادگی** خود را به صورت کامل وارد نمایید:", reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(AuthStates.entering_name, F.text)
async def process_name_input(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await state.set_state(AuthStates.waiting_for_phone)
    await message.answer(
        "📱 لطفاً شماره تماس خود را ارسال کنید.\n"
        "می‌توانید دکمه زیر را لمس کنید یا شماره خود را تایپ نمایید:",
        reply_markup=phone_request_keyboard()
    )

@dp.message(AuthStates.waiting_for_phone, F.contact | F.text)
async def process_phone_input(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text.strip()
    data = await state.get_data()
    role = data.get("role", "student")
    full_name = data.get("full_name", message.from_user.full_name)

    await save_user(message.from_user.id, role, full_name, phone)
    await state.clear()

    # ارسال نوتیفیکیشن فوری ثبت‌نام کاربر جدید به ادمین و پشتیبانی
    admin_notify = (
        f"⚡️ **ثبت‌نام جدید در ربات زینگو!**\n\n"
        f"👤 نام: **{full_name}**\n"
        f"🎭 نقش: **{'🎓 زبان‌آموز' if role == 'student' else '👨‍🏫 متقاضی تدریس / استاد'}**\n"
        f"📱 شماره: `{phone}`\n"
        f"🆔 آیدی کاربری: `{message.from_user.id}`\n"
        f"🔗 یوزرنیم: @{message.from_user.username if message.from_user.username else 'ندارد'}"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_notify, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error sending admin notification: {e}")

    # هدایت به منوی مرتبط
    if role == "student":
        await message.answer(
            f"✅ اطلاعات شما با موفقیت ثبت شد {full_name} عزیز!\n"
            "اکنون می‌توانید از خدمات آکادمی زینگو استفاده فرمایید:",
            reply_markup=student_main_menu()
        )
    else:
        await message.answer(
            f"✅ استاد {full_name} گرامی، به سامانه مدرسین آکادمی زینگو خوش آمدید.\n"
            "لطفاً رزومه و نمونه تدریس خود را ارسال فرمایید:",
            reply_markup=teacher_main_menu()
        )

# --- جریان تعیین سطح کتبی (۴۰ سوال CEFR) ---
@dp.message(F.text == "📝 تعیین سطح آنلاین (۴۰ سوال)")
async def start_placement_test(message: types.Message, state: FSMContext):
    await state.set_state(PlacementStates.answering)
    await state.update_data(score=0, current_q=0)
    
    q_data = QUESTIONS[0]
    await message.answer(
        "🎯 **آزمون تعیین سطح آکادمی زینگو (A1 تا C1)**\n"
        "این آزمون ۴۰ سوال دارد و به صورت دقیق سطح گرامر و ساختار شما را ارزیابی می‌کند.\n\n"
        f"**سوال ۱ از ۴۰:** (سطح {q_data['level']})\n{q_data['q']}",
        reply_markup=question_keyboard(0, q_data['options']),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    _, q_idx_str, selected_opt_str = callback.data.split("_")
    q_idx = int(q_idx_str)
    selected_opt = int(selected_opt_str)

    data = await state.get_data()
    score = data.get("score", 0)

    if selected_opt == QUESTIONS[q_idx]["answer"]:
        score += 1

    next_q = q_idx + 1

    if next_q < len(QUESTIONS):
        await state.update_data(score=score, current_q=next_q)
        q_data = QUESTIONS[next_q]
        await callback.message.edit_text(
            f"**سوال {next_q + 1} از ۴۰:** (سطح {q_data['level']})\n{q_data['q']}",
            reply_markup=question_keyboard(next_q, q_data['options']),
            parse_mode="Markdown"
        )
    else:
        result = calculate_cefr_level(score)
        await state.clear()
        
        await save_placement_result(callback.from_user.id, score, result['level'])
        user_info_db = await get_user(callback.from_user.id)
        user_name = user_info_db[2] if user_info_db else callback.from_user.full_name
        user_phone = user_info_db[3] if user_info_db else "ثبت نشده"

        report_user = (
            f"🏁 **نتیجه آزمون تعیین سطح شما ({user_name}):**\n\n"
            f"📊 **نمره نهایی:** {score} از ۴۰\n"
            f"🎯 **سطح تخمینی:** `{result['level']}`\n"
            f"📝 **توضیحات:** {result['desc']}\n"
            f"💡 **پیشنهاد زینگو:** {result['course']}\n\n"
            f"📞 جهت هماهنگی و مشاوره رایگان با {SUPPORT_ID} در ارتباط باشید."
        )
        await callback.message.edit_text(report_user, parse_mode="Markdown")

        # ارسال گزارش آزمون به ادمین با مشخصات کامل
        report_admin = (
            f"📊 **کارنامه آزمون تعیین سطح ۴۰ سؤالی!**\n\n"
            f"👤 داوطلب: **{user_name}**\n"
            f"📱 شماره: `{user_phone}`\n"
            f"🆔 شناسه تلگرام: `{callback.from_user.id}`\n"
            f"🔗 یوزرنیم: @{callback.from_user.username if callback.from_user.username else 'ندارد'}\n"
            f"📈 نمره: **{score}/40**\n"
            f"🎯 سطح تعیین‌شده: **{result['level']}**\n"
            f"📚 دوره پیشنهادی: {result['course']}"
        )
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=report_admin, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Error sending placement report to admin: {e}")

    await callback.answer()

# --- جریان ارسال ویس اسپیکینگ (شفاهی) به ادمین ---
@dp.message(F.text == "🎙 ارسال ویس اسپیکینگ")
async def request_voice(message: types.Message, state: FSMContext):
    await state.set_state(VoiceStates.waiting_for_voice)
    prompt_text = (
        "🎙 **آزمون ارزیابی اسپیکینگ آکادمی زینگو**\n\n"
        "لطفاً یک ویس حدوداً ۱ الی ۲ دقیقه‌ای به زبان انگلیسی ضبط و ارسال نمایید و به این موضوع پاسخ دهید:\n\n"
        "👉 *'Introduce yourself, describe your educational or professional background, and explain why you want to master English.'*\n\n"
        "⚠️ ویس شما مستقیماً برای اساتید و مدیریت زینگو ارسال شده و نتیجه آن به اطلاعتان خواهد رسید."
    )
    await message.answer(prompt_text, parse_mode="Markdown")

@dp.message(VoiceStates.waiting_for_voice, F.voice)
async def receive_voice(message: types.Message, state: FSMContext):
    user_info_db = await get_user(message.from_user.id)
    user_name = user_info_db[2] if user_info_db else message.from_user.full_name
    user_phone = user_info_db[3] if user_info_db else "ثبت نشده"
    level = user_info_db[5] if user_info_db else "تعیین نشده"

    caption_for_admin = (
        f"🎙 **ویس تعیین سطح اسپیکینگ جدید!**\n\n"
        f"👤 داوطلب: **{user_name}**\n"
        f"📱 شماره تماس: `{user_phone}`\n"
        f"🎯 سطح کتبی قبلی: `{level}`\n"
        f"🆔 شناسه: `{message.from_user.id}`\n"
        f"🔗 آیدی تلگرام: @{message.from_user.username if message.from_user.username else 'ندارد'}"
    )

    try:
        # ارسال ویس به همراه شناسنامه دقیق به ادمین
        await bot.send_voice(
            chat_id=ADMIN_ID,
            voice=message.voice.file_id,
            caption=caption_for_admin,
            parse_mode="Markdown"
        )
        await message.answer(
            "✅ ویس اسپیکینگ شما با موفقیت برای تیم اساتید زینگو ارسال شد.\n"
            "ارزیابی شما به زودی انجام و نتیجه اعلام می‌شود.",
            reply_markup=student_main_menu()
        )
    except Exception as e:
        logging.error(f"Error forwarding voice to admin: {e}")
        await message.answer("⚠️ متأسفانه در ارسال ویس خطایی رخ داد. لطفاً با پشتیبانی در تماس باشید.")

    await state.clear()

# --- جریان ارسال فیش واریزی مستقیم به ادمین ---
@dp.message(F.text == "💳 ارسال فیش واریزی")
async def start_receipt_flow(message: types.Message, state: FSMContext):
    await state.set_state(ReceiptStates.waiting_for_course)
    await message.answer("لطفاً نام دوره‌ای که برای آن واریز کرده‌اید را بنویسید (مثلاً: تکنیک‌های آیلتس، TTC، Speak Now یا تصحیح رایتینگ):")

@dp.message(ReceiptStates.waiting_for_course, F.text)
async def process_receipt_course(message: types.Message, state: FSMContext):
    await state.update_data(course_name=message.text.strip())
    await state.set_state(ReceiptStates.waiting_for_receipt)
    await message.answer("لطفاً تصویر (عکس) فیش واریزی خود را ارسال نمایید:")

@dp.message(ReceiptStates.waiting_for_receipt, F.photo)
async def process_receipt_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    course = data.get("course_name", "ثبت‌نشده")
    photo_file_id = message.photo[-1].file_id

    user_info_db = await get_user(message.from_user.id)
    user_name = user_info_db[2] if user_info_db else message.from_user.full_name
    user_phone = user_info_db[3] if user_info_db else "ثبت نشده"

    await save_receipt(message.from_user.id, course, photo_file_id)

    admin_caption = (
        f"💳 **رسید / فیش واریزی جدید!**\n\n"
        f"👤 نام واریزکننده: **{user_name}**\n"
        f"📱 تلفن: `{user_phone}`\n"
        f"📚 دوره: **{course}**\n"
        f"🆔 شناسه: `{message.from_user.id}`\n"
        f"🔗 یوزرنیم: @{message.from_user.username if message.from_user.username else 'ندارد'}"
    )

    try:
        await bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_file_id,
            caption=admin_caption,
            parse_mode="Markdown"
        )
        await message.answer(
            "✅ فیش واریزی شما با موفقیت به واحد مالی زینگو تحویل داده شد.\n"
            "همکاران ما پس از بررسی با شما هماهنگ خواهند شد.",
            reply_markup=student_main_menu()
        )
    except Exception as e:
        logging.error(f"Error forwarding receipt to admin: {e}")
        await message.answer("⚠️ خطا در ارسال فیش. لطفاً مجدداً امتحان کنید.")

    await state.clear()

# --- پنل و جریان‌های همکاری اساتید ---
@dp.message(F.text == "📋 تکمیل و ارسال فرم همکاری تدریس")
async def teacher_form_start(message: types.Message, state: FSMContext):
    await state.set_state(TeacherStates.waiting_for_info)
    await message.answer(
        "👨‍🏫 **فرم جذب مدرس آکادمی زینگو**\n\n"
        "لطفاً به صورت مختصر سوابق تدریس، مدارک بین‌المللی (مانند TTC, CELTA, IELTS) و حوزه‌هایی که توانایی تدریس دارید را بنویسید:"
    )

@dp.message(TeacherStates.waiting_for_info, F.text)
async def teacher_info_received(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text.strip())
    await state.set_state(TeacherStates.waiting_for_resume)
    await message.answer("لطفاً فایل رزومه خود را (PDF یا Word) ارسال کنید (اگر ندارید، عبارت 'ندارم' را تایپ کنید):")

@dp.message(TeacherStates.waiting_for_resume, F.document | F.text)
async def teacher_resume_received(message: types.Message, state: FSMContext):
    doc_id = message.document.file_id if message.document else "none"
    await state.update_data(resume_file_id=doc_id)
    await state.set_state(TeacherStates.waiting_for_demo)
    await message.answer(
        "🎙 لطفاً یک ویس کوتاه ۳ تا ۵ دقیقه‌ای به عنوان نمونه تدریس (Demo Teaching) به زبان انگلیسی ضبط و ارسال فرمایید:"
    )

@dp.message(TeacherStates.waiting_for_demo, F.voice)
async def teacher_demo_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    exp = data.get("experience", "ثبت نشده")
    resume_id = data.get("resume_file_id", "none")
    demo_id = message.voice.file_id

    user_info_db = await get_user(message.from_user.id)
    user_name = user_info_db[2] if user_info_db else message.from_user.full_name
    user_phone = user_info_db[3] if user_info_db else "ثبت نشده"

    await save_teacher_application(message.from_user.id, exp, "IELTS/General", resume_id, demo_id)

    # گزارش به ادمین
    admin_msg = (
        f"👨‍🏫 **درخواست همکاری تدریس جدید!**\n\n"
        f"👤 متقاضی: **{user_name}**\n"
        f"📱 تلفن: `{user_phone}`\n"
        f"📝 سوابق و توضیحات: {exp}\n"
        f"🆔 شناسه: `{message.from_user.id}`\n"
        f"🔗 آیدی: @{message.from_user.username if message.from_user.username else 'ندارد'}"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")
        await bot.send_voice(chat_id=ADMIN_ID, voice=demo_id, caption=f"🎙 ویس دمو تدریس {user_name}")
        if resume_id != "none":
            await bot.send_document(chat_id=ADMIN_ID, document=resume_id, caption=f"📄 رزومه {user_name}")
        
        await message.answer("✅ پرونده همکاری شما با موفقیت برای مدیریت آموزشی زینگو ارسال شد. به زودی با شما تماس خواهیم گرفت.", reply_markup=teacher_main_menu())
    except Exception as e:
        logging.error(f"Error forwarding teacher application: {e}")

    await state.clear()

@dp.message(F.text == "🔄 تغییر نقش به زبان‌آموز")
async def switch_to_student(message: types.Message):
    user_info = await get_user(message.from_user.id)
    name = user_info[2] if user_info else message.from_user.full_name
    phone = user_info[3] if user_info else ""
    await save_user(message.from_user.id, "student", name, phone)
    await message.answer("🔄 دسترسی شما به پنل زبان‌آموز تغییر یافت.", reply_markup=student_main_menu())

# --- منوی دوره‌ها و اطلاعات ---
@dp.message(F.text == "📚 دوره‌های آموزشی زینگو")
async def show_courses_menu(message: types.Message):
    await message.answer(
        "📚 **دوره‌های تخصصی آکادمی زبان زینگو (بر بستر بیگ‌بلو‌باتن):**\n\n"
        "برای مشاهده جزئیات هر دوره، دکمه مورد نظر را لمس کنید:",
        reply_markup=courses_inline_keyboard()
    )

@dp.callback_query(F.data.startswith("c_"))
async def course_details_handler(callback: types.CallbackQuery):
    c_map = {
        "c_ttc": "🎓 **دوره تربیت مدرس TTC**\n⏱ ۱۵ جلسه کاربردی\n💰 شهریه: ۸,۹۰۰,۰۰۰ تومان\nآموزش تکنیک‌های مدرن تدریس آنلاین و ارائه مدرک پایان دوره.",
        "c_ielts": "🚀 **دوره تکنیک‌های جامع IELTS / TOEFL**\n⏱ ۱۵ جلسه فوق تخصصی\n💰 شهریه: ۱۹,۵۰۰,۰۰۰ تومان\nآموزش مهارت‌های چهارگانه به همراه آزمون‌های ماک تحلیلی.",
        "c_speak": "🗣 **دوره‌های مکالمه Speak Now**\n⏱ ۸ جلسه نیمه‌خصوصی\n💰 شهریه: ۲,۸۰۰,۰۰۰ تومان\nتمرکز کامل بر افزایش روانی کلام (Fluency) و تلفظ صحیح.",
        "c_general": "📖 **دوره‌های جامع ترمیک Cutting Edge**\n⏱ پکیج‌های استاندارد ترمیک\n💰 شهریه: از ۴,۲۰۰,۰۰۰ تا ۹,۰۰۰,۰۰۰ تومان."
    }
    desc = c_map.get(callback.data, "اطلاعات دوره یافت نشد.")
    await callback.message.edit_text(desc, reply_markup=courses_inline_keyboard(), parse_mode="Markdown")
    await callback.answer()

# --- پشتیبانی و تصحیح رایتینگ ---
@dp.message(F.text.in_(["📞 پشتیبانی و مشاوره", "📞 ارتباط مستقیم با مدیریت آموزشی"]))
async def support_info(message: types.Message):
    await message.answer(
        "📞 **راه‌های ارتباط با پشتیبانی و مدیریت آکادمی زینگو:**\n\n"
        f"💬 ارتباط مستقیم تلگرام: {SUPPORT_ID}\n"
        f"📱 تماس و واتساپ: `{SUPPORT_PHONE}`\n"
        "🌐 وب‌سایت رسمی: https://zingoielts.ir\n"
        "📸 اینستاگرام: `ielts_with_zahra`\n\n"
        "⏰ ساعت پاسخگویی: ۹ صبح الی ۲۱",
        parse_mode="Markdown"
    )

@dp.message(F.text == "✍️ تصحیح تخصصی رایتینگ")
async def writing_service_info(message: types.Message):
    await message.answer(
        "✍️ **سامانه تصحیح تحلیلی رایتینگ IELTS / TOEFL**\n\n"
        "• تصحیح کلمه به کلمه Task 1 و Task 2\n"
        "• آنالیز بر اساس معیارهای چهارگانه اگزمینر (TR, CC, LR, GRA)\n"
        "• نمره‌دهی دقیق + ارائه نسخه بازنویسی شده (Sample 8+)\n"
        "💰 تعرفه: ۳۵۰,۰۰۰ الی ۵۵۰,۰۰۰ تومان\n\n"
        f"جهت ارسال فایل رایتینگ، به {SUPPORT_ID} پیام دهید.",
        parse_mode="Markdown"
    )

# --- استارت پولینگ و راه‌اندازی دیتابیس ---
async def main():
    await init_db()
    logging.info("Zingo Academy Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

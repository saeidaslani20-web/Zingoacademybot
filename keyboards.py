# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def role_selection_keyboard():
    keyboard = [
        [KeyboardButton(text="🎓 من زبان‌آموز هستم"), KeyboardButton(text="👨‍🏫 من مدرس / متقاضی تدریس هستم")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def phone_request_keyboard():
    keyboard = [
        [KeyboardButton(text="📱 ارسال شماره تماس من", request_contact=True)]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def student_main_menu():
    keyboard = [
        [KeyboardButton(text="📝 تعیین سطح آنلاین (۴۰ سوال)"), KeyboardButton(text="🎙 ارسال ویس اسپیکینگ")],
        [KeyboardButton(text="📚 دوره‌های آموزشی زینگو"), KeyboardButton(text="💳 ارسال فیش واریزی")],
        [KeyboardButton(text="✍️ تصحیح تخصصی رایتینگ"), KeyboardButton(text="📞 پشتیبانی و مشاوره")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def teacher_main_menu():
    keyboard = [
        [KeyboardButton(text="📋 تکمیل و ارسال فرم همکاری تدریس"), KeyboardButton(text="🎙 ارسال نمونه تدریس (Demo)")],
        [KeyboardButton(text="📞 ارتباط مستقیم با مدیریت آموزشی"), KeyboardButton(text="🔄 تغییر نقش به زبان‌آموز")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def courses_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="🎓 دوره تربیت مدرس TTC (۱۵ جلسه)", callback_data="c_ttc")],
        [InlineKeyboardButton(text="🚀 تکنیک‌های IELTS / TOEFL (۱۵ جلسه)", callback_data="c_ielts")],
        [InlineKeyboardButton(text="🗣 دوره‌های مکالمه Speak Now", callback_data="c_speak")],
        [InlineKeyboardButton(text="📖 دوره‌های ترمیک عمومی Cutting Edge", callback_data="c_general")],
        [InlineKeyboardButton(text="💬 ارتباط با پشتیبانی جهت مشاوره", url="https://t.me/Zingo_ielts")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def question_keyboard(q_idx: int, options: list):
    buttons = []
    for idx, opt in enumerate(options):
        buttons.append([InlineKeyboardButton(text=opt, callback_data=f"ans_{q_idx}_{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

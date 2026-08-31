# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def student_main_menu():
    keyboard = [
        [KeyboardButton(text="📝 تعیین سطح آنلاین (۴۰ سوال)"), KeyboardButton(text="🎙 ارسال ویس اسپیکینگ")],
        [KeyboardButton(text="📚 مشاهده دوره‌ها و تصحیح رایتینگ"), KeyboardButton(text="💳 ارسال فیش واریزی")],
        [KeyboardButton(text="📞 پشتیبانی و مشاوره")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def courses_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="🎓 دوره تربیت مدرس TTC", callback_data="c_ttc")],
        [InlineKeyboardButton(text="🚀 تکنیک‌های IELTS / TOEFL", callback_data="c_ielts")],
        [InlineKeyboardButton(text="🗣 دوره‌های مکالمه Speak Now", callback_data="c_speak")],
        [InlineKeyboardButton(text="✍️ تصحیح تخصصی رایتینگ", callback_data="c_writing")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# سایر کیبوردها (role_selection_keyboard, phone_request_keyboard, question_keyboard, teacher_main_menu)
# همانند کدهای قبلی باقی می‌مانند.

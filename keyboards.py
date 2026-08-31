from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def role_selection_keyboard():
    keyboard = [
        [KeyboardButton(text="🎓 زبان‌آموز"), KeyboardButton(text="👨‍🏫 متقاضی تدریس / استاد")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def phone_request_keyboard():
    keyboard = [
        [KeyboardButton(text="📱 ارسال خودکار شماره تماس", request_contact=True)]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def student_main_menu():
    keyboard = [
        [KeyboardButton(text="📝 تعیین سطح آنلاین (۴۰ سوال)"), KeyboardButton(text="🎙 ارسال ویس اسپیکینگ")],
        [KeyboardButton(text="📚 مشاهده دوره‌ها و تصحیح رایتینگ"), KeyboardButton(text="💳 ارسال فیش واریزی")],
        [KeyboardButton(text="📞 پشتیبانی و مشاوره")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def teacher_main_menu():
    keyboard = [
        [KeyboardButton(text="📄 ارسال رزومه و مدارک")],
        [KeyboardButton(text="📞 پشتیبانی و مشاوره")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def courses_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="🎓 دوره تربیت مدرس TTC", callback_data="c_ttc")],
        [InlineKeyboardButton(text="🚀 دوره‌های تخصصی IELTS / TOEFL", callback_data="c_ielts")],
        [InlineKeyboardButton(text="🗣 دوره‌های مکالمه Speak Now", callback_data="c_speak")],
        [InlineKeyboardButton(text="✍️ تصحیح تخصصی رایتینگ (Writing)", callback_data="c_writing")],
        [InlineKeyboardButton(text="🔙 بستن منو", callback_data="close_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def question_keyboard(options, q_index):
    keyboard = []
    for idx, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(text=opt, callback_data=f"ans_{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    kb = [
        [KeyboardButton(text="🎯 آزمون و تعیین سطح آنلاین"), KeyboardButton(text="📚 معرفی دوره‌ها و شهریه")],
        [KeyboardButton(text="👨‍🏫 کلاس‌های من / ورود به BBB"), KeyboardButton(text="💳 ثبت فیش واریزی")],
        [KeyboardButton(text="📞 ارتباط با پشتیبانی و مشاوره")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def share_phone_keyboard():
    kb = [
        [KeyboardButton(text="📱 ارسال شماره تماس", request_contact=True)],
        [KeyboardButton(text="❌ انصراف")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)

def quiz_options_keyboard(q_idx: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data=f"ans_{q_idx}_A"), InlineKeyboardButton(text="B", callback_data=f"ans_{q_idx}_B")],
        [InlineKeyboardButton(text="C", callback_data=f"ans_{q_idx}_C"), InlineKeyboardButton(text="D", callback_data=f"ans_{q_idx}_D")]
    ])

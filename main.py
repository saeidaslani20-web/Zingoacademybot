import re
# ... سایر import ها ...

# تابع اعتبارسنجی
def is_persian_name(text):
    return bool(re.match(r'^[\u0600-\u06FF\s]+$', text))

def is_valid_phone(text):
    return bool(re.match(r'^09\d{9}$', text))

# --- در بخش AuthStates ---
@dp.message(AuthStates.entering_name, F.text)
async def process_name_input(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not is_persian_name(name):
        await message.answer("⚠️ لطفاً نام خود را فقط با حروف فارسی وارد کنید.")
        return
    await state.update_data(full_name=name)
    await state.set_state(AuthStates.waiting_for_phone)
    await message.answer("📱 لطفاً شماره تماس خود را (با فرمت ۰۹...) وارد کنید:", reply_markup=phone_request_keyboard())

@dp.message(AuthStates.waiting_for_phone, F.text | F.contact)
async def process_phone_input(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text.strip()
    if not is_valid_phone(phone):
        await message.answer("⚠️ شماره تماس وارد شده معتبر نیست. لطفاً با فرمت ۰۹۱۲۳۴۵۶۷۸۹ وارد کنید.")
        return
    
    # ... ادامه ذخیره‌سازی و ثبت‌نام ...

# --- جریان جدید رایتینگ (در بخش FSM و Handlers) ---
class WritingStates(StatesGroup):
    waiting_for_receipt = State()
    waiting_for_file = State()

@dp.callback_query(F.data == "c_writing")
async def start_writing_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(WritingStates.waiting_for_receipt)
    await callback.message.answer("✍️ برای سرویس تصحیح رایتینگ، ابتدا تصویر فیش واریزی خود را ارسال کنید:")
    await callback.answer()

@dp.message(WritingStates.waiting_for_receipt, F.photo)
async def get_writing_receipt(message: types.Message, state: FSMContext):
    await state.update_data(receipt_id=message.photo[-1].file_id)
    await state.set_state(WritingStates.waiting_for_file)
    await message.answer("✅ رسید دریافت شد. حالا لطفاً فایل رایتینگ خود را (PDF یا Word) ارسال کنید:")

@dp.message(WritingStates.waiting_for_file, F.document)
async def get_writing_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    receipt_id = data.get("receipt_id")
    file_id = message.document.file_id
    
    # ارسال به ادمین
    admin_msg = f"✍️ **درخواست جدید تصحیح رایتینگ**\nکاربر: {message.from_user.full_name}\nآیدی: `{message.from_user.id}`"
    await bot.send_photo(chat_id=ADMIN_ID, photo=receipt_id, caption=admin_msg)
    await bot.send_document(chat_id=ADMIN_ID, document=file_id)
    
    await message.answer("✅ فیش و فایل شما با موفقیت به واحد آموزشی ارسال شد. پاسخ طی ۴۸ ساعت برای شما ارسال می‌شود.\n\n📞 پشتیبانی: 00989104446166 | @Zingo_ielts")
    await state.clear()

# --- در بخش نمایش نتیجه تعیین سطح ---
    result = calculate_cefr_level(score)
    # ... (کدهای محاسبه) ...
    report_user = (
        f"🏁 **نتیجه نهایی آزمون:**\n📊 نمره: {score}/40\n🎯 سطح: {result['level']}\n💡 پیشنهاد: {result['course']}\n\n"
        f"📞 برای مشاوره با پشتیبانی تماس بگیرید:\nشماره: `00989104446166`\nآیدی: @Zingo_ielts"
    )
    await callback.message.edit_text(report_user, parse_mode="Markdown")

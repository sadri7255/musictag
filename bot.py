import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pydub import AudioSegment
import os
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# توکن ربات شما
TOKEN = "7197743010:AAF8kYM5tcFsfShRpyUmevS0BkrV2osPQ5I"
bot = telebot.TeleBot(TOKEN)

# تنظیمات Google Sheets
SPREADSHEET_ID = "1uCYP6-fwmcvYEvfqAz53U9OJmHQ2N2A86TmnJNpVNO4"  # ID گوگل شیت شما
SHEET_NAME = "Sheet1"  # نام شیت مورد نظر

# تنظیمات ربات
TEMP_FOLDER = "temp_audio"
os.makedirs(TEMP_FOLDER, exist_ok=True)

MAX_FILE_SIZE_MB = 25
user_states = {}

STATE_WAITING_AUDIO = "waiting_audio"
STATE_WAITING_OPTIONS = "waiting_options"

# تابع برای ایجاد credentials از Environment Variables
def create_credentials_from_env():
    credentials = {
        "type": os.getenv("GOOGLE_TYPE"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace("\\n", "\n"),
        "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL"),
        "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN")
    }
    return credentials

# تابع برای اتصال به Google Sheets
def connect_to_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = create_credentials_from_env()
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1  # استفاده از اولین شیت
    return sheet

# تابع برای ذخیره اطلاعات کاربر در Google Sheets
def save_user_info_to_sheet(user_id, username):
    sheet = connect_to_google_sheets()
    sheet.append_row([user_id, username])  # اضافه کردن اطلاعات به انتهای شیت

# دستور شروع
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.chat.id
    username = message.chat.username or "Unknown"
    
    # ذخیره اطلاعات کاربر در Google Sheets
    save_user_info_to_sheet(user_id, username)
    
    user_states[user_id] = {"state": STATE_WAITING_AUDIO}
    bot.send_message(user_id, "👋 سلام! لطفاً فایل صوتی خود را ارسال کنید.")

# دریافت فایل صوتی
@bot.message_handler(content_types=['audio', 'voice'])
def process_audio(message):
    user_id = message.chat.id
    state = user_states.get(user_id, {})
    if state.get('state') != STATE_WAITING_AUDIO:
        bot.send_message(user_id, "❌ لطفاً ابتدا فایل صوتی را ارسال کنید!")
        return

    try:
        file_id = message.audio.file_id if message.audio else message.voice.file_id
        file_info = bot.get_file(file_id)

        # بررسی حجم فایل
        file_size_mb = file_info.file_size / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            bot.send_message(user_id, f"⚠️ فایل ارسالی بزرگ‌تر از {MAX_FILE_SIZE_MB} مگابایت است.")
            return

        # ارسال پیام اولیه و ذخیره message_id برای به‌روزرسانی
        processing_message = bot.send_message(user_id, "🔄 در حال پردازش فایل صوتی...")
        user_states[user_id]['processing_message_id'] = processing_message.message_id

        # دانلود فایل
        downloaded_file = bot.download_file(file_info.file_path)
        audio_data = io.BytesIO(downloaded_file)

        # ذخیره داده در حافظه
        user_states[user_id]['audio_data'] = audio_data
        user_states[user_id]['state'] = STATE_WAITING_OPTIONS

        # نمایش دکمه‌های شیشه‌ای
        show_options(user_id)

    except Exception as e:
        bot.send_message(user_id, f"❌ خطا: {str(e)}")

# نمایش دکمه‌های شیشه‌ای
def show_options(chat_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("تغییر نام آلبوم", callback_data="change_title"),
        InlineKeyboardButton("تغییر نام هنرمند", callback_data="change_artist"),
        InlineKeyboardButton("کم کردن حجم فایل", callback_data="reduce_size"),
        InlineKeyboardButton("ثبت تغییرات و ارسال فایل", callback_data="save_and_send")
    )
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=user_states[chat_id]['processing_message_id'],
        text="🎛️ لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=keyboard
    )

# پردازش انتخاب کاربر
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    state = user_states.get(chat_id, {})

    if call.data == "change_title":
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=state['processing_message_id'],
            text="📝 لطفاً نام جدید آلبوم را وارد کنید:"
        )
        user_states[chat_id]['next_action'] = "set_title"
    elif call.data == "change_artist":
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=state['processing_message_id'],
            text="📝 لطفاً نام جدید هنرمند را وارد کنید:"
        )
        user_states[chat_id]['next_action'] = "set_artist"
    elif call.data == "reduce_size":
        reduce_audio_size(chat_id)
    elif call.data == "save_and_send":
        save_and_send_audio(chat_id)

# دریافت عنوان جدید
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('next_action') == "set_title")
def set_title(message):
    user_id = message.chat.id
    user_states[user_id]['title'] = message.text
    user_states[user_id]['next_action'] = None
    bot.edit_message_text(
        chat_id=user_id,
        message_id=user_states[user_id]['processing_message_id'],
        text=f"✅ عنوان آلبوم به **{message.text}** تغییر یافت."
    )
    show_options(user_id)

# دریافت نام هنرمند جدید
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('next_action') == "set_artist")
def set_artist(message):
    user_id = message.chat.id
    user_states[user_id]['artist'] = message.text
    user_states[user_id]['next_action'] = None
    bot.edit_message_text(
        chat_id=user_id,
        message_id=user_states[user_id]['processing_message_id'],
        text=f"✅ نام هنرمند به **{message.text}** تغییر یافت."
    )
    show_options(user_id)

# کم کردن حجم فایل
def reduce_audio_size(chat_id):
    state = user_states.get(chat_id, {})
    try:
        audio_data = state.get('audio_data')
        audio = AudioSegment.from_file(audio_data)
        reduced_audio = audio.set_frame_rate(16000).set_channels(1)  # کاهش کیفیت
        user_states[chat_id]['audio_data'] = reduced_audio
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=state['processing_message_id'],
            text="✅ حجم فایل با موفقیت کاهش یافت."
        )
        show_options(chat_id)
    except Exception as e:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=state['processing_message_id'],
            text=f"❌ خطا در کاهش حجم فایل: {str(e)}"
        )

# ثبت تغییرات و ارسال فایل
def save_and_send_audio(chat_id):
    state = user_states.get(chat_id, {})
    try:
        audio = state.get('audio_data')
        title = state.get('title', "Unknown Title")
        artist = state.get('artist', "Unknown Artist")

        processed_file = io.BytesIO()
        audio.export(processed_file, format="mp3", tags={"title": title, "artist": artist})
        processed_file.seek(0)

        # ارسال فایل به کاربر
        bot.send_audio(chat_id, processed_file, title=title, performer=artist)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=state['processing_message_id'],
            text="✅ فایل با موفقیت ارسال شد."
        )

        # بازگشت به حالت اولیه و نمایش دکمه‌های شیشه‌ای جدید
        user_states[chat_id] = {"state": STATE_WAITING_AUDIO}
        show_new_file_options(chat_id)

    except Exception as e:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=state['processing_message_id'],
            text=f"❌ خطا در ارسال فایل: {str(e)}"
        )

# نمایش دکمه‌های شیشه‌ای جدید پس از ارسال فایل
def show_new_file_options(chat_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("ارسال فایل جدید", callback_data="new_file")
    )
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=user_states[chat_id]['processing_message_id'],
        text="🎉 فایل شما ارسال شد! آیا می‌خواهید فایل جدیدی ارسال کنید؟",
        reply_markup=keyboard
    )

# پردازش انتخاب کاربر برای فایل جدید
@bot.callback_query_handler(func=lambda call: call.data == "new_file")
def handle_new_file(call):
    chat_id = call.message.chat.id
    user_states[chat_id] = {"state": STATE_WAITING_AUDIO}
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=user_states[chat_id]['processing_message_id'],
        text="👋 لطفاً فایل صوتی جدید خود را ارسال کنید."
    )

# اجرای ربات
bot.infinity_polling()

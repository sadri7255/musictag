import telebot
from pydub import AudioSegment
import os
import io
import concurrent.futures

TOKEN = "7679134239:AAEvzmtJTZPSzDF1-bYrNcJsxlcRrENwpbA"
bot = telebot.TeleBot(TOKEN)

TEMP_FOLDER = "temp_audio"
os.makedirs(TEMP_FOLDER, exist_ok=True)

MAX_FILE_SIZE_MB = 25
user_states = {}

STATE_WAITING_AUDIO = "waiting_audio"
STATE_WAITING_TITLE = "waiting_title"
STATE_WAITING_ARTIST = "waiting_artist"
STATE_PROCESSING = "processing"

# خوشامدگویی
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 سلام! لطفاً ابتدا فایل صوتی خود را ارسال کنید.")
    user_states[message.chat.id] = {"state": STATE_WAITING_AUDIO}

# پردازش فایل صوتی
@bot.message_handler(content_types=['audio', 'voice'])
def process_audio(message):
    state = user_states.get(message.chat.id, {})
    if state.get('state') != STATE_WAITING_AUDIO:
        bot.reply_to(message, "❌ لطفاً ابتدا فایل صوتی را ارسال کنید!")
        return

    try:
        file_id = message.audio.file_id if message.audio else message.voice.file_id
        file_info = bot.get_file(file_id)

        # بررسی حجم فایل
        file_size_mb = file_info.file_size / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            bot.reply_to(message, f"⚠️ فایل ارسالی بزرگ‌تر از {MAX_FILE_SIZE_MB} مگابایت است.")
            return

        downloading_message = bot.reply_to(message, "🔄 در حال دانلود فایل صوتی...")

        # دانلود فایل در حافظه
        downloaded_file = bot.download_file(file_info.file_path)
        audio_data = io.BytesIO(downloaded_file)

        # ذخیره داده در حافظه برای پردازش
        user_states[message.chat.id]['audio_data'] = audio_data
        user_states[message.chat.id]['state'] = STATE_WAITING_TITLE

        bot.edit_message_text("🎵 فایل صوتی دریافت شد. حالا لطفاً **عنوان (Title)** را وارد کنید.",
                              chat_id=downloading_message.chat.id, message_id=downloading_message.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {str(e)}")

# دریافت Title
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('state') == STATE_WAITING_TITLE)
def receive_title(message):
    user_states[message.chat.id]['title'] = message.text
    user_states[message.chat.id]['state'] = STATE_WAITING_ARTIST
    bot.reply_to(message, f"✅ عنوان ذخیره شد: **{message.text}**\n🎤 حالا لطفاً **نام هنرمند (Artist)** را وارد کنید.")

# دریافت Artist و پردازش فایل
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('state') == STATE_WAITING_ARTIST)
def receive_artist(message):
    user_states[message.chat.id]['artist'] = message.text
    user_states[message.chat.id]['state'] = STATE_PROCESSING
    process_and_send_audio(message)

# پردازش فایل و ارسال
def process_and_send_audio(message):
    state = user_states.get(message.chat.id, {})
    try:
        processing_message = bot.reply_to(message, "🔄 در حال پردازش فایل... لطفاً صبر کنید.")

        audio_data = state.get('audio_data')
        title = state.get('title', "Unknown Title")
        artist = state.get('artist', "Unknown Artist")

        audio = AudioSegment.from_file(audio_data)
        processed_audio = audio.set_frame_rate(16000).set_channels(1)

        processed_file = io.BytesIO()
        processed_audio.export(processed_file, format="mp3", tags={"title": title, "artist": artist})
        processed_file.seek(0)

        bot.edit_message_text("✅ پردازش فایل کامل شد. در حال ارسال...",
                              chat_id=processing_message.chat.id, message_id=processing_message.message_id)

        bot.send_audio(message.chat.id, processed_file, title=title, performer=artist)
        user_states[message.chat.id] = {"state": STATE_WAITING_AUDIO}

    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {str(e)}")

# اجرای ربات
bot.infinity_polling()

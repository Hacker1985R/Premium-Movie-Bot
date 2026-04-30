import telebot
from telebot import types
import json
import os
import re
import difflib # Matches dhundhne ke liye

# --- DETAILS ---
API_TOKEN = "8719355883:AAFXKXO4lntJ3RhtzH9-mQJjD9j9_KvWr1w"
ADMIN_ID = 5853568437 # Apni ID dalo
# ---------------

bot = telebot.TeleBot(API_TOKEN)
DB_FILE = 'database.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f: return json.load(f)
    return {"movie": {}, "anime": {}, "webseries": {}}

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

db = load_db()

# --- Welcome Interface ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎬 Movies", callback_data="help_movie")
    btn2 = types.InlineKeyboardButton("⛩️ Anime", callback_data="help_anime")
    btn3 = types.InlineKeyboardButton("📺 Series", callback_data="help_series")
    btn4 = types.InlineKeyboardButton("📩 Request", callback_data="help_req")
    markup.add(btn1, btn2, btn3, btn4)
    
    welcome_text = (
        f"✨ *Premium Movie Radar*\n\n"
        f"Hello *{message.from_user.first_name}*,\n"
        "Main aapka personal entertainment assistant hoon. "
        "Niche diye gaye buttons ka use karein ya seedha search karein!"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# --- Admin Panel (Sirf Aapke Liye) ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        text = (
            "🛠 *ADMIN CONTROL PANEL*\n\n"
            "➕ *Add (text only):*\n`/add movie | name | link`\n\n"
            "🖼 *Add with poster:*\nPhoto bhejein, uske *caption* me likhein:\n`/add movie | name | link`\n\n"
            "🗑 *Delete:* `/del movie | name`"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "🚫 Access Denied.")

# --- Search with Suggestions ---
@bot.message_handler(commands=['movie', 'anime', 'webseries'])
def search(message):
    cmd = message.text.split()[0][1:].lower()
    query = message.text.replace(f'/{cmd} ', '').strip().lower()

    all_names = list(db[cmd].keys())
    found_key = None

    if query in db[cmd]:
        found_key = query
    else:
        # Partial match: agar query kisi name ka hissa hai
        partial = [n for n in all_names if query in n or n in query]
        if len(partial) == 1:
            found_key = partial[0]

    if found_key:
        data = db[cmd][found_key]
        raw_link = data.get('link', '').replace('\\n', '\n')
        photo = data.get('photo', '')

        # Har URL aur uske aas-paas ka quality label nikaalo
        url_pattern = re.compile(r'(https?://\S+)')
        url_matches = list(url_pattern.finditer(raw_link))

        def detect_label(text_before, idx, total):
            # Common quality keywords
            qualities = ["2160p", "4k", "1440p", "1080p", "720p", "480p", "360p",
                         "hdrip", "webrip", "bluray", "hdcam", "hd"]
            tb = text_before.lower()
            for q in qualities:
                if q in tb:
                    return q.upper()
            # Fallback default labels
            defaults = ["480p", "720p", "1080p", "4K", "HD"]
            return defaults[idx] if idx < len(defaults) else f"Link {idx+1}"

        markup = types.InlineKeyboardMarkup()
        caption = f"🌟 *{found_key.upper()}*\n\n"

        if len(url_matches) == 1:
            markup.add(types.InlineKeyboardButton(
                "🚀 Download / Watch Online", url=url_matches[0].group(1)))
            caption += "✅ Content ready! Niche button par click karein."
        elif len(url_matches) > 1:
            prev_end = 0
            for i, m in enumerate(url_matches):
                # Text just before this URL (since previous URL ended)
                text_before = raw_link[prev_end:m.start()]
                label = detect_label(text_before, i, len(url_matches))
                markup.add(types.InlineKeyboardButton(
                    f"📥 {label}", url=m.group(1)))
                prev_end = m.end()
            caption += "✅ Content ready! Quality select karein:"
        else:
            caption += raw_link

        rm = markup if url_matches else None
        sent = False
        if photo:
            try:
                bot.send_photo(
                    message.chat.id,
                    photo,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=rm
                )
                sent = True
            except Exception as e:
                print(f"send_photo failed: {e}")
        if not sent:
            bot.send_message(
                message.chat.id,
                caption,
                parse_mode="Markdown",
                reply_markup=rm
            )
    else:
        # Suggestions Logic — partial + fuzzy
        partial = [n for n in all_names if query in n or n in query]
        fuzzy = difflib.get_close_matches(query, all_names, n=3, cutoff=0.3)
        matches = list(dict.fromkeys(partial + fuzzy))[:5]

        msg = f"🔍 *'{query}'* nahi mili."
        if matches:
            msg += "\n\n💡 *Shayad aap ye dhundh rahe hain:*\n"
            for m in matches:
                msg += f"• `/{cmd} {m}`\n"

        msg += f"\n📩 Request karne ke liye: `/request {query}`"
        bot.reply_to(message, msg, parse_mode="Markdown")

# --- Add Content ---
def _process_add(message, raw_text, photo_id=None):
    try:
        p = raw_text.replace('/add', '', 1).strip().split('|')
        cat = p[0].strip().lower()
        name = p[1].strip().lower()
        link = p[2].strip() if len(p) > 2 else ''
        photo = photo_id or (p[3].strip() if len(p) > 3 else '')

        if cat not in db:
            db[cat] = {}

        db[cat][name] = {"link": link, "photo": photo}
        save_db(db)
        photo_note = "📸 Photo attached" if photo else "📭 Without photo"
        bot.reply_to(
            message,
            f"⭐ *Successfully Added:* {name.upper()}\n{photo_note}",
            parse_mode="Markdown"
        )
    except Exception:
        bot.reply_to(
            message,
            "❌ *Format:*\n"
            "`/add movie | Jawan | link`\n"
            "_(photo bhejna ho to photo ke caption me yahi command likhein)_",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['add'])
def add_content(message):
    if message.from_user.id == ADMIN_ID:
        _process_add(message, message.text)

# Photo ke saath caption me /add aaye to photo ko poster bana lo
@bot.message_handler(content_types=['photo'],
                     func=lambda m: (m.caption or '').strip().lower().startswith('/add'))
def add_with_photo(message):
    if message.from_user.id == ADMIN_ID:
        # Sabse bade size ka photo file_id lo
        photo_id = message.photo[-1].file_id
        _process_add(message, message.caption, photo_id=photo_id)

# --- Delete Content (Admin Only) ---
@bot.message_handler(commands=['del'])
def delete_content(message):
    if message.from_user.id == ADMIN_ID:
        try:
            p = message.text.replace('/del ', '').split('|')
            cat, name = p[0].strip().lower(), p[1].strip().lower()
            if name in db[cat]:
                del db[cat][name]
                save_db(db)
                bot.reply_to(message, f"🗑️ *Deleted:* {name}")
            else:
                bot.reply_to(message, "❌ Not found.")
        except:
            bot.reply_to(message, "❌ Use: `/del movie | name`")

# --- Request ---
@bot.message_handler(commands=['request'])
def req(message):
    r = message.text.replace('/request ', '')
    bot.reply_to(message, "✅ Admin ko request bhej di gayi hai!")
    bot.send_message(ADMIN_ID, f"📩 *New Request:* {r}\nFrom: {message.from_user.first_name}")

# Callback for buttons
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    help_msgs = {
        "help_movie": "🎬 Movie ke liye likhein: `/movie Jawan`",
        "help_anime": "⛩️ Anime ke liye likhein: `/anime Naruto`",
        "help_series": "📺 Series ke liye likhein: `/webseries Mirzapur`",
        "help_req": "📩 Request ke liye: `/request MovieName`"
    }
    try:
        bot.answer_callback_query(call.id, help_msgs.get(call.data, "?"), show_alert=True)
    except Exception as e:
        print(f"Callback error: {e}")

print("Premium Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)

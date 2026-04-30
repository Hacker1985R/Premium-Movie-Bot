import telebot
from telebot import types
import json
import os
import re
import difflib # Matches dhundhne ke liye

# --- DETAILS (Secrets se load — code me visible nahi) ---
API_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

if not API_TOKEN or not ADMIN_ID:
    raise RuntimeError(
        "❌ BOT_TOKEN aur ADMIN_ID Secrets me set karein. "
        "Replit ke Secrets tab me jaake add karein."
    )
# -------------------------------------------------------

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
        display = data.get('display_name') or found_key.upper()
        caption = f"🌟 *{display}*\n\n"

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
        body = raw_text.replace('/add', '', 1).strip()

        # Pehla separator: category aur baki ke beech (sirf '|')
        first = body.find('|')
        if first == -1:
            raise ValueError("Need at least: /add cat | name")
        cat = body[:first].strip().lower()
        rest = body[first + 1:].strip()

        # Doosra separator: name aur links ke beech — '|' ya newline, jo pehle aaye
        nl = rest.find('\n')
        pipe = rest.find('|')
        candidates = [x for x in [nl, pipe] if x != -1]
        if candidates:
            sep = min(candidates)
            name_raw = rest[:sep].strip()
            link_block = rest[sep + 1:].strip()
        else:
            name_raw = rest.strip()
            link_block = ''

        if not name_raw:
            raise ValueError("Name required")

        name_key = name_raw.lower()

        if cat not in db:
            db[cat] = {}

        db[cat][name_key] = {
            "display_name": name_raw,   # Original case preserved
            "link": link_block,          # URLs ka case as-is
            "photo": photo_id or ''
        }
        save_db(db)

        photo_note = "📸 Photo attached" if photo_id else "📭 No photo"
        bot.reply_to(
            message,
            f"⭐ *Successfully Added:* {name_raw}\n{photo_note}",
            parse_mode="Markdown"
        )
    except Exception:
        bot.reply_to(
            message,
            "❌ *Format:*\n"
            "`/add movie | Movie Name | links...`\n\n"
            "*Ya phir:*\n"
            "`/add movie | Movie Name`\n"
            "`📥 480p :- https://...`\n"
            "`📥 720p :- https://...`\n\n"
            "_Photo attach karne ke liye photo bhejein aur uske caption me yahi command likhein._",
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

# --- Inline Mode (YouTube-jaisa live suggestions) ---
# User kisi bhi chat me likhe: @aapka_bot doom  -> live suggestions aayengi
@bot.inline_handler(func=lambda q: True)
def inline_search(inline_query):
    try:
        q = inline_query.query.strip().lower()
        results = []
        idx = 0

        # Sabhi categories me se matching items dhundo
        for cat, items in db.items():
            for key, data in items.items():
                if q == "" or q in key or key in q:
                    display = data.get('display_name') or key.upper()
                    raw_link = data.get('link', '').replace('\\n', '\n')
                    urls = re.findall(r'https?://\S+', raw_link)
                    photo = data.get('photo', '')

                    # Buttons banao
                    markup = types.InlineKeyboardMarkup()
                    if len(urls) == 1:
                        markup.add(types.InlineKeyboardButton(
                            "🚀 Download / Watch", url=urls[0]))
                    elif len(urls) > 1:
                        defaults = ["480p", "720p", "1080p", "4K", "HD"]
                        for i, u in enumerate(urls):
                            label = defaults[i] if i < len(defaults) else f"Link {i+1}"
                            markup.add(types.InlineKeyboardButton(
                                f"📥 {label}", url=u))

                    caption = f"🌟 *{display}*\n\n📂 _{cat.title()}_"

                    # Agar photo file_id hai (Telegram-uploaded), to photo result
                    # Agar URL hai aur image jaisa lagta hai, photo result
                    # Warna article result
                    if photo and photo.startswith('http'):
                        results.append(types.InlineQueryResultPhoto(
                            id=str(idx),
                            photo_url=photo,
                            thumbnail_url=photo,
                            title=display,
                            description=cat.title(),
                            caption=caption,
                            parse_mode="Markdown",
                            reply_markup=markup
                        ))
                    else:
                        results.append(types.InlineQueryResultArticle(
                            id=str(idx),
                            title=display,
                            description=f"{cat.title()} • Tap to share",
                            input_message_content=types.InputTextMessageContent(
                                caption, parse_mode="Markdown"),
                            reply_markup=markup
                        ))
                    idx += 1
                    if idx >= 30:  # Telegram limit ~50
                        break
            if idx >= 30:
                break

        if not results:
            results.append(types.InlineQueryResultArticle(
                id="0",
                title="❌ Kuch nahi mila",
                description=f"'{inline_query.query}' database me nahi hai",
                input_message_content=types.InputTextMessageContent(
                    f"📩 Request: /request {inline_query.query}")
            ))

        bot.answer_inline_query(inline_query.id, results, cache_time=1)
    except Exception as e:
        print(f"Inline error: {e}")

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

import telebot
from telebot import types
import json
import os
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
            "➕ *Add:* `/add cat | name | link | photo` \n"
            "🗑 *Del:* `/del cat | name`"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "🚫 Access Denied.")

# --- Search with Suggestions ---
@bot.message_handler(commands=['movie', 'anime', 'webseries'])
def search(message):
    cmd = message.text.split()[0][1:].lower()
    query = message.text.replace(f'/{cmd} ', '').strip().lower()

    if query in db[cmd]:
        data = db[cmd][query]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Download / Watch Online", url=data['link']))
        
        bot.send_photo(
            message.chat.id, 
            data['photo'], 
            caption=f"🌟 *{query.upper()}*\n\n✅ Content ready! Niche button par click karein.",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        # Suggestions Logic
        all_names = list(db[cmd].keys())
        matches = difflib.get_close_matches(query, all_names, n=3, cutoff=0.3)
        
        msg = f"🔍 *'{query}'* nahi mili."
        if matches:
            msg += "\n\n💡 *Shayad aap ye dhundh rahe hain:*\n"
            for m in matches:
                msg += f"• `/{cmd} {m}`\n"
        
        msg += f"\n📩 Request karne ke liye: `/request {query}`"
        bot.reply_to(message, msg, parse_mode="Markdown")

# --- Add Content ---
@bot.message_handler(commands=['add'])
def add_content(message):
    if message.from_user.id == ADMIN_ID:
        try:
            p = message.text.replace('/add ', '').split('|')
            cat, name, link, photo = p[0].strip().lower(), p[1].strip().lower(), p[2].strip(), p[3].strip()
            db[cat][name] = {"link": link, "photo": photo}
            save_db(db)
            bot.reply_to(message, f"⭐ *Successfully Added:* {name.upper()}", parse_mode="Markdown")
        except:
            bot.reply_to(message, "❌ Format: `/add movie | Jawan | link | photo`", parse_mode="Markdown")

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
    bot.answer_callback_query(call.id, help_msgs[call.data], show_alert=True)

print("Premium Bot is running...")
bot.polling()

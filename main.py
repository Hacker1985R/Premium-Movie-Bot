from keep_alive import keep_alive
import telebot
from telebot import types
import json
import os
import re
import threading
import difflib # Matches dhundhne ke liye

# --- Auto-Delete Settings ---
AUTO_DELETE_SECONDS = 120  # 2 minutes

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

# --- Requests storage ---
REQ_FILE = 'requests.json'

def load_reqs():
    if os.path.exists(REQ_FILE):
        with open(REQ_FILE, 'r') as f: return json.load(f)
    return []

def save_reqs(data):
    with open(REQ_FILE, 'w') as f: json.dump(data, f, indent=4)

requests_db = load_reqs()

# --- Auto-delete helper ---
def schedule_delete(chat_id, message_id, delay=AUTO_DELETE_SECONDS):
    def _del():
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            print(f"Auto-delete failed: {e}")
    t = threading.Timer(delay, _del)
    t.daemon = True
    t.start()

# --- Welcome Interface ---
@bot.message_handler(commands=['start'])
def start(message):
    db = load_db()
    movie_count = len(db.get("movie", {}))
    anime_count = len(db.get("anime", {}))
    series_count = len(db.get("webseries", {}))

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton(f"🎬 Movies ({movie_count})", callback_data="help_movie")
    btn2 = types.InlineKeyboardButton(f"⛩️ Anime ({anime_count})", callback_data="help_anime")
    btn3 = types.InlineKeyboardButton(f"📺 Series ({series_count})", callback_data="help_series")
    btn4 = types.InlineKeyboardButton("📩 Request", callback_data="help_req")
    markup.add(btn1, btn2, btn3, btn4)
    
    total = movie_count + anime_count + series_count
    welcome_text = (
        f"╔══════════════════════╗\n"
        f"  🎬 *PREMIUM MOVIE RADAR* 🎬\n"
        f"╚══════════════════════╝\n\n"
        f"👋 Welcome, *{message.from_user.first_name}*!\n\n"
        f"🗄 *Database:* `{total}` titles available\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 *Search karo ya category chunein:*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 _Tip: /movie Pushpa — seedha search bhi kar sakte ho!_"
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
            "🗑 *Delete:* `/del movie | name`\n\n"
            "📩 *Requests dekho:* `/requests`\n"
            "🧹 *Clear done/rejected:* `/clearreq`"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "🚫 Access Denied.")

# --- Search with Suggestions ---
@bot.message_handler(commands=['movie', 'anime', 'webseries'])
def search(message):
    cmd = message.text.split()[0][1:].lower()
    query = message.text.replace(f'/{cmd} ', '').strip().lower()

    # Minimum 2 characters required
    if len(query) < 2:
        bot.reply_to(
            message,
            "✏️ Kam se kam *2 letters* likho search karne ke liye.\n"
            "Example: `/movie kd` ya `/movie pushpa`",
            parse_mode="Markdown"
        )
        return

    all_names = list(db[cmd].keys())
    found_key = None

    if query in db[cmd]:
        found_key = query
    else:
        # Partial match: sirf tab match karo jab query kam se kam 2 chars ho
        # aur movie name me query ka 2+ char ka hissa mile
        partial = [
            n for n in all_names
            if len(query) >= 2 and (query in n or n.startswith(query[:2]))
            and query[:2] in n  # kam se kam pehle 2 letters match hone chahiye
        ]
        # Sirf tab auto-select karo jab exact 1 match ho
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
        caption = (
            f"┌──────────────────────\n"
            f"  🎬 *{display}*\n"
            f"└──────────────────────\n\n"
        )

        if len(url_matches) == 1:
            markup.add(types.InlineKeyboardButton(
                "🚀 Download / Watch Online", url=url_matches[0].group(1)))
            caption += "✅ *Ready to Watch!*\n📥 Niche button dabao aur enjoy karo!"
        elif len(url_matches) > 1:
            prev_end = 0
            for i, m in enumerate(url_matches):
                text_before = raw_link[prev_end:m.start()]
                label = detect_label(text_before, i, len(url_matches))
                markup.add(types.InlineKeyboardButton(
                    f"📥 {label}", url=m.group(1)))
                prev_end = m.end()
            caption += "✅ *Multiple Qualities Available!*\n🎯 Apni pasand ki quality select karo:"
        else:
            caption += raw_link

        # Admin ke liye remove button
        if message.from_user.id == ADMIN_ID:
            import urllib.parse
            safe_key = urllib.parse.quote(f"{cmd}|{found_key}", safe='')
            markup.add(types.InlineKeyboardButton(
                "🗑 Remove Movie", callback_data=f"remove_{safe_key}"))

        # Auto-delete warning (sirf non-admin ke liye)
        if message.from_user.id != ADMIN_ID:
            mins = AUTO_DELETE_SECONDS // 60
            caption += f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n⏳ _Ye message {mins} min me delete hoga — link save kar lo!_"

        rm = markup
        sent_msg = None
        if photo:
            try:
                sent_msg = bot.send_photo(
                    message.chat.id,
                    photo,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=rm
                )
            except Exception as e:
                print(f"send_photo failed: {e}")
        if sent_msg is None:
            sent_msg = bot.send_message(
                message.chat.id,
                caption,
                parse_mode="Markdown",
                reply_markup=rm
            )

        # Auto-delete sirf non-admin ke liye
        if sent_msg and message.from_user.id != ADMIN_ID:
            schedule_delete(sent_msg.chat.id, sent_msg.message_id)
    else:
        # Suggestions — sirf meaningful matches dikhao
        partial = [
            n for n in all_names
            if len(query) >= 2 and query[:2] in n and query in n
        ]
        fuzzy = difflib.get_close_matches(query, all_names, n=5, cutoff=0.4)
        matches = list(dict.fromkeys(partial + fuzzy))[:5]

        msg = (
            f"╔══════════════════════╗\n"
            f"  🔍 Search Result\n"
            f"╚══════════════════════╝\n\n"
            f"😔 *'{query}'* nahi mili database mein.\n\n"
        )
        if matches:
            msg += "💡 *Shayad aap ye dhundh rahe hain:*\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            for m in matches:
                display = db[cmd][m].get('display_name') or m
                msg += f"▸ `/{cmd} {m}` — _{display}_\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        else:
            msg += "❌ _Koi milti-julti title nahi mili._\n\n"

        msg += f"\n📩 *Request karo:* `/request {query}`\n_Admin jald se jald add karega!_"
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

        photo_note = "📸 _Poster attached_" if photo_id else "📭 _No poster_"
        bot.reply_to(
            message,
            f"╔══════════════════════╗\n"
            f"  ✅ Successfully Added!\n"
            f"╚══════════════════════╝\n\n"
            f"🎬 *{name_raw}*\n"
            f"📂 Category: `{cat}`\n"
            f"{photo_note}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Database update ho gaya!_",
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
    import time
    r = message.text.replace('/request', '', 1).strip()
    if not r:
        bot.reply_to(message, "❌ Likhein: `/request Movie Name`", parse_mode="Markdown")
        return

    user = message.from_user
    entry = {
        "id": int(time.time() * 1000),
        "movie": r,
        "user_id": user.id,
        "user_name": user.first_name or "",
        "username": f"@{user.username}" if user.username else "",
        "time": time.strftime("%d %b %Y, %I:%M %p"),
        "status": "pending"
    }
    requests_db.append(entry)
    save_reqs(requests_db)

    bot.reply_to(message, (
        f"╔══════════════════════╗\n"
        f"  📩 Request Submitted!\n"
        f"╚══════════════════════╝\n\n"
        f"✅ *'{r}'* ki request admin ko bhej di gayi!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ _Jaise hi available hogi, aapko notify kar diya jayega!_"
    ), parse_mode="Markdown")

    # Admin ko notification + quick action button
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Mark Added", callback_data=f"req_done_{entry['id']}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"req_rej_{entry['id']}")
    )
    uname = entry['username'] or entry['user_name']
    bot.send_message(
        ADMIN_ID,
        f"╔══════════════════════╗\n"
        f"  📩 NEW REQUEST ALERT!\n"
        f"╚══════════════════════╝\n\n"
        f"🎬 *Title:* {r}\n"
        f"👤 *User:* {uname} (`{user.id}`)\n"
        f"🕒 *Time:* {entry['time']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=markup
    )

# --- Admin: View all requests ---
@bot.message_handler(commands=['requests'])
def list_requests(message):
    if message.from_user.id != ADMIN_ID:
        return

    pending = [r for r in requests_db if r['status'] == 'pending']
    done = [r for r in requests_db if r['status'] == 'done']
    rejected = [r for r in requests_db if r['status'] == 'rejected']

    if not requests_db:
        bot.reply_to(message, "📭 Koi request nahi hai abhi tak.")
        return

    text = f"📊 *Requests Summary*\n\n"
    text += f"⏳ Pending: {len(pending)}\n"
    text += f"✅ Done: {len(done)}\n"
    text += f"❌ Rejected: {len(rejected)}\n\n"

    if pending:
        text += "*━━━ ⏳ PENDING ━━━*\n"
        for r in pending[-15:]:  # Last 15
            uname = r['username'] or r['user_name']
            text += f"\n🎬 *{r['movie']}*\n👤 {uname} • 🕒 {r['time']}\n"

    bot.reply_to(message, text, parse_mode="Markdown")

    # Pending walo ke liye quick action buttons (last 5)
    for r in pending[-5:]:
        uname = r['username'] or r['user_name']
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Mark Added", callback_data=f"req_done_{r['id']}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"req_rej_{r['id']}")
        )
        bot.send_message(
            ADMIN_ID,
            f"🎬 *{r['movie']}*\n👤 {uname} (`{r['user_id']}`)\n🕒 {r['time']}",
            parse_mode="Markdown",
            reply_markup=markup
        )

# --- Admin: Clear old/done requests ---
@bot.message_handler(commands=['clearreq'])
def clear_requests(message):
    if message.from_user.id != ADMIN_ID:
        return
    global requests_db
    before = len(requests_db)
    requests_db = [r for r in requests_db if r['status'] == 'pending']
    save_reqs(requests_db)
    bot.reply_to(message, f"🗑️ {before - len(requests_db)} purani requests delete ho gayi.")

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
    try:
        # Help buttons (welcome screen ke)
        help_msgs = {
            "help_movie": "🎬 MOVIES\n\nSearch karo:\n/movie Pushpa\n/movie Jawan\n/movie KGF",
            "help_anime": "⛩️ ANIME\n\nSearch karo:\n/anime Naruto\n/anime Dragon Ball\n/anime AOT",
            "help_series": "📺 WEB SERIES\n\nSearch karo:\n/webseries Mirzapur\n/webseries Money Heist",
            "help_req": "📩 REQUEST\n\nJo movie chahiye:\n/request Pushpa 2\n/request KGF 3\n\nAdmin jald add karega!"
        }
        if call.data in help_msgs:
            bot.answer_callback_query(call.id, help_msgs[call.data], show_alert=True)
            return

        # Request management buttons (admin only)
        if call.data.startswith("req_"):
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "🚫 Sirf admin ke liye", show_alert=True)
                return

            parts = call.data.split("_")
            action = parts[1]  # done / rej
            req_id = int(parts[2])

            target = next((r for r in requests_db if r['id'] == req_id), None)
            if not target:
                bot.answer_callback_query(call.id, "❌ Request not found", show_alert=True)
                return

            if action == "done":
                target['status'] = 'done'
                save_reqs(requests_db)
                bot.answer_callback_query(call.id, "✅ Marked as added")
                # User ko notify karo
                try:
                    bot.send_message(
                        target['user_id'],
                        f"╔══════════════════════╗\n"
                        f"  🎉 Request Complete!\n"
                        f"╚══════════════════════╝\n\n"
                        f"✅ *'{target['movie']}'* ab available hai!\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🔍 Ab search karo:\n`/movie {target['movie']}`",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"User notify failed: {e}")
                # Update message
                try:
                    bot.edit_message_text(
                        f"✅ *DONE:* {target['movie']}",
                        call.message.chat.id, call.message.message_id,
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            elif action == "rej":
                target['status'] = 'rejected'
                save_reqs(requests_db)
                bot.answer_callback_query(call.id, "❌ Rejected")
                try:
                    bot.send_message(
                        target['user_id'],
                        f"╔══════════════════════╗\n"
                        f"  😔 Request Update\n"
                        f"╚══════════════════════╝\n\n"
                        f"❌ *'{target['movie']}'* abhi available nahi hai.\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"_Baad me dobara try karo ya koi aur title request karo._",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"User notify failed: {e}")
                try:
                    bot.edit_message_text(
                        f"❌ *REJECTED:* {target['movie']}",
                        call.message.chat.id, call.message.message_id,
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            return

        # Remove movie button (admin only)
        if call.data.startswith("remove_"):
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "🚫 Sirf admin ke liye!", show_alert=True)
                return
            import urllib.parse
            raw = urllib.parse.unquote(call.data.replace("remove_", "", 1))
            parts = raw.split("|", 1)
            if len(parts) == 2:
                cat, name = parts[0], parts[1]
                if cat in db and name in db[cat]:
                    display = db[cat][name].get('display_name') or name
                    del db[cat][name]
                    save_db(db)
                    bot.answer_callback_query(call.id, f"🗑 '{display}' delete ho gayi!", show_alert=True)
                    try:
                        bot.edit_message_caption(
                            caption=f"🗑 *{display}* — Delete ho gayi!",
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            parse_mode="Markdown"
                        )
                    except Exception:
                        try:
                            bot.edit_message_text(
                                f"🗑 *{display}* — Delete ho gayi!",
                                call.message.chat.id,
                                call.message.message_id,
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                else:
                    bot.answer_callback_query(call.id, "❌ Movie already delete ho chuki hai.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "?")
    except Exception as e:
        print(f"Callback error: {e}")

if os.environ.get("KEEP_ALIVE", "false").lower() == "true":
    keep_alive()
print("Premium Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)

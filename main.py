
"""
FlexTeaBot — Smart. Friendly. Anonymous.
Created by: Renjith Rajeev (@thisisrenjith)
"""

from flask import Flask, request
from telegram import Update, Bot, constants
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import os
import logging
import re

# === Logging ===
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === Environment Variables ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = f"https://flextea.onrender.com/webhook/{BOT_TOKEN}"

# === Flask App ===
app = Flask(__name__)
bot_app = None

# === In-memory storage ===
verified_users = {}
user_groups = {}
message_inbox = {}
comfort_queue = {}

CATEGORIES = ["Gossip", "Suggestion", "Complaint", "Appreciation"]
AUDIENCES = ["My Office", "A Specific Store", "A Specific Team", "All Flexway"]

# === Emotion Filter ===
def emotion_shield(text):
    rude_words = ["sucks", "hate", "stupid", "idiot", "trash", "useless", "dog"]
    if any(w in text.lower() for w in rude_words):
        return False
    if re.search(r"\b(hr|admin|finance|manager|it)\b.*\b(sucks|lazy|idiot|trash)\b", text.lower()):
        return False
    return True

# === Telegram Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
 f"👋 Hey {user.first_name or 'there'}! Welcome to FlexTea 🍵"

"
        "Welcome to FlexTea 🍵 — your anonymous sharing bot.

"
        "🧭 First, reply with your *Outlet/Team Name* to verify."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Outlet registration
    if user_id not in verified_users:
        verified_users[user_id] = True
        user_groups[user_id] = {"group": text}
        await update.message.reply_text(f"✅ You’re verified under group: {text}")
        return

    # Start spill
    if text.lower() == "/spill":
        cat_msg = "📢 What would you like to post?
" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)])
        await update.message.reply_text(cat_msg)
        return

    # Handle category selection
    if text.isdigit() and int(text) in range(1, len(CATEGORIES)+1):
        category = CATEGORIES[int(text)-1]
        verified_users[user_id] = {"category": category}
        aud_msg = "👥 Who should see this?
" + "\n".join([f"{i+1}. {a}" for i, a in enumerate(AUDIENCES)])
        await update.message.reply_text(aud_msg)
        return

    # Audience selection
    if isinstance(verified_users[user_id], dict) and "category" in verified_users[user_id]:
        if text.isdigit() and int(text) in range(1, len(AUDIENCES)+1):
            audience = AUDIENCES[int(text)-1]
            verified_users[user_id]["audience"] = audience
            await update.message.reply_text("💬 Now type your message to post anonymously:")
            return

        # Final message posting
        if "audience" in verified_users[user_id]:
            if not emotion_shield(text):
                await update.message.reply_text("⚠️ Please rephrase your message politely.")
                return

            category = verified_users[user_id]["category"]
            audience = verified_users[user_id]["audience"]
            msg_id = f"MSG{len(message_inbox)+1}"
            message_inbox[msg_id] = user_id
            comfort_queue[msg_id] = []

            group = user_groups[user_id]["group"]
            targets = [uid for uid, g in user_groups.items()
                       if audience == "All Flexway" or g["group"] == group]

            for t_id in targets:
                if t_id != user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=t_id,
                            text=f"🍵 *{category}* #{msg_id}\n{text}\n\n💬 Reply anonymously: /reply {msg_id}",
                            parse_mode=constants.ParseMode.MARKDOWN
                        )
                    except:
                        pass

            await update.message.reply_text("✅ Your message was posted anonymously.")
            verified_users[user_id] = True
            return

    # Handle /reply MSGID
    if text.startswith("/reply"):
        parts = text.split()
        if len(parts) == 2 and parts[1] in message_inbox:
            comfort_queue[parts[1]].append((user_id, "Pending reply"))
            await update.message.reply_text("✏️ Type your anonymous reply now:")
            return
        await update.message.reply_text("❌ Invalid format. Use /reply MSG1")
        return

    # Send anonymous reply
    for msg_id, replies in comfort_queue.items():
        for i, (uid, status) in enumerate(replies):
            if uid == user_id and status == "Pending reply":
                comfort_queue[msg_id][i] = (uid, text)
                original_user = message_inbox[msg_id]
                await context.bot.send_message(
                    chat_id=original_user,
                    text=f"💌 Anonymous reply to #{msg_id}:
{text}"
                )
                await update.message.reply_text("✅ Reply sent anonymously.")
                return

# === Register Handlers ===
@app.route("/")
def index():
    return "FlexTea is live ☕️"

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
async def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}

@app.before_first_request
def set_webhook():
    bot = Bot(BOT_TOKEN)
    import asyncio
    asyncio.run(bot.set_webhook(WEBHOOK_URL))

# === Launch App ===
if __name__ == "__main__":
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

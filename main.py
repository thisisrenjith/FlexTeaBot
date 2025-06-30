from flask import Flask, request
from telegram import Update, Bot, constants
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import os
import logging
import re
import asyncio

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = "7971742600:AAGUhFXL7m9qyJTuMmmCGOEk-40xC7SpJRg"
WEBHOOK_URL = f"https://flextea.onrender.com/webhook/{BOT_TOKEN}"

app = Flask(__name__)
bot_app = None

verified_users = {}
user_groups = {}
message_inbox = {}
comfort_queue = {}

CATEGORIES = ["Gossip", "Suggestion", "Complaint", "Appreciation"]
AUDIENCES = ["My Office", "A Specific Store", "A Specific Team", "All Flexway"]

def emotion_shield(text):
    rude_words = ["sucks", "hate", "stupid", "idiot", "trash", "useless", "dog"]
    if any(w in text.lower() for w in rude_words):
        return False
    if re.search(r"\b(hr|admin|finance|manager|it)\b.*\b(sucks|lazy|idiot|trash)\b", text.lower()):
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        f"👋 Hey {user.first_name or 'there'}!\n"
        "Welcome to FlexTea 🍵 — your anonymous sharing bot.\n\n"
        "🧽 First, reply with your *Outlet/Team Name* to verify."
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_verification(user_id, text, update):
    verified_users[user_id] = True
    user_groups[user_id] = {"group": text}
    await update.message.reply_text(f"✅ You’re verified under group: {text}")

async def prompt_category(update):
    cat_msg = "📢 What would you like to post?\n" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)])
    await update.message.reply_text(cat_msg)

async def prompt_audience(update):
    aud_msg = "👥 Who should see this?\n" + "\n".join([f"{i+1}. {a}" for i, a in enumerate(AUDIENCES)])
    await update.message.reply_text(aud_msg)

async def post_message(user_id, text, context, update):
    category = verified_users[user_id]["category"]
    audience = verified_users[user_id]["audience"]
    msg_id = f"MSG{len(message_inbox)+1}"
    message_inbox[msg_id] = user_id
    comfort_queue[msg_id] = []

    group = user_groups[user_id]["group"]
    targets = [uid for uid, g in user_groups.items() if audience == "All Flexway" or g["group"] == group]

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

async def handle_reply_command(text, user_id, update):
    parts = text.split()
    if len(parts) == 2 and parts[1] in message_inbox:
        comfort_queue[parts[1]].append((user_id, "Pending reply"))
        await update.message.reply_text("✏️ Type your anonymous reply now:")
    else:
        await update.message.reply_text("❌ Invalid format. Use /reply MSG1")

async def handle_pending_reply(user_id, text, context, update):
    for msg_id, replies in comfort_queue.items():
        for i, (uid, status) in enumerate(replies):
            if uid == user_id and status == "Pending reply":
                comfort_queue[msg_id][i] = (uid, text)
                original_user = message_inbox[msg_id]
                await context.bot.send_message(
                    chat_id=original_user,
                    text=f"💌 Anonymous reply to #{msg_id}:\n{text}"
                )
                await update.message.reply_text("✅ Reply sent anonymously.")
                return True
    return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in verified_users:
        await handle_verification(user_id, text, update)
        return

    if text.lower() == "/spill":
        await prompt_category(update)
        return

    if text.isdigit() and int(text) in range(1, len(CATEGORIES)+1):
        if not isinstance(verified_users[user_id], dict):
            verified_users[user_id] = {}
        verified_users[user_id]["category"] = CATEGORIES[int(text)-1]
        await prompt_audience(update)
        return

    if isinstance(verified_users[user_id], dict) and "category" in verified_users[user_id]:
        if text.isdigit() and int(text) in range(1, len(AUDIENCES)+1):
            verified_users[user_id]["audience"] = AUDIENCES[int(text)-1]
            await update.message.reply_text("💬 Now type your message to post anonymously:")
            return

        if "audience" in verified_users[user_id]:
            if not emotion_shield(text):
                await update.message.reply_text("⚠️ Please rephrase your message politely.")
                return
            await post_message(user_id, text, context, update)
            return

    if text.startswith("/reply"):
        await handle_reply_command(text, user_id, update)
        return

    if await handle_pending_reply(user_id, text, context, update):
        return

    await update.message.reply_text("❓ I didn’t get that. Try /spill to start or type your outlet/team name if new.")

@app.route("/")
def index():
    return "FlexTea is live ☕️"

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
async def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}

if __name__ == "__main__":
    async def run():
        global bot_app
        bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(MessageHandler(filters.TEXT, handle_message))

        bot = Bot(BOT_TOKEN)
        await bot.set_webhook(WEBHOOK_URL)

        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)

    asyncio.run(run())
from flask import Flask, request
import os
from telegram import Update, Bot, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import asyncio
import re

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
application = ApplicationBuilder().token(BOT_TOKEN).build()

verified_users = {}
user_groups = {}
message_inbox = {}
comfort_queue = {}

CATEGORIES = ["Gossip", "Suggestion", "Complaint", "Appreciation"]
AUDIENCES = ["My Office", "A Specific Store", "A Specific Team", "All Flexway"]

def emotion_shield(text):
    rude_keywords = ["sucks", "hate", "stupid", "useless", "idiot", "dog", "trash"]
    if any(word in text.lower() for word in rude_keywords):
        return False
    if re.search(r"\b(it|hr|finance|manager|admin)\b.*\b(sucks|idiot|trash|lazy)\b", text.lower()):
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to FlexTea 🍵\nPlease reply with your Office/Store/Team name for verification.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in verified_users:
        verified_users[user_id] = True
        user_groups[user_id] = {"group": text}
        await update.message.reply_text(f"✅ You are verified under group: {text}.")
        return

    if text.lower() == "/spill":
        cat_msg = "What would you like to post?\n" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)])
        await update.message.reply_text(cat_msg)
        return

    if text.isdigit() and int(text) in range(1, len(CATEGORIES)+1):
        category = CATEGORIES[int(text) - 1]
        verified_users[user_id] = {"category": category}
        aud_msg = "Who should see this message?\n" + "\n".join([f"{i+1}. {a}" for i, a in enumerate(AUDIENCES)])
        await update.message.reply_text(aud_msg)
        return

    if user_id in verified_users and isinstance(verified_users[user_id], dict) and "category" in verified_users[user_id]:
        if text.isdigit() and int(text) in range(1, len(AUDIENCES)+1):
            audience = AUDIENCES[int(text) - 1]
            verified_users[user_id]["audience"] = audience
            await update.message.reply_text("Please type your message now.")
            return

        if "audience" in verified_users[user_id]:
            category = verified_users[user_id]["category"]
            audience = verified_users[user_id]["audience"]
            msg_text = text

            if not emotion_shield(msg_text):
                await update.message.reply_text("⚠️ Please rephrase your message in a respectful way.")
                return

            msg_id = f"MSG{len(message_inbox)+1}"
            message_inbox[msg_id] = user_id
            comfort_queue[msg_id] = []

            target_users = [uid for uid, group in user_groups.items()
                            if audience == "All Flexway" or group["group"] == user_groups[user_id]["group"]]

            for target_id in target_users:
                if target_id != user_id:
                    try:
                        await context.bot.send_message(chat_id=target_id,
                            text=f"🍵 *{category}* #{msg_id}\n{msg_text}\n\nReply anonymously? Type: /reply {msg_id}",
                            parse_mode=constants.ParseMode.MARKDOWN)
                    except:
                        continue

            await update.message.reply_text("✅ Your message has been posted anonymously.")
            verified_users[user_id] = True
            return

    if text.startswith("/reply"):
        parts = text.split()
        if len(parts) == 2:
            msg_id = parts[1]
            if msg_id in message_inbox:
                comfort_queue[msg_id].append((user_id, "Pending reply"))
                await update.message.reply_text("✏️ Type your anonymous reply now:")
        else:
            await update.message.reply_text("❌ Invalid reply format. Use /reply MSG1")
        return

    for mid, replies in comfort_queue.items():
        for i, (uid, status) in enumerate(replies):
            if uid == user_id and status == "Pending reply":
                comfort_queue[mid][i] = (uid, text)
                original_user = message_inbox[mid]
                await context.bot.send_message(chat_id=original_user,
                                               text=f"💌 Anonymous reply to your message #{mid}:\n{text}")
                await update.message.reply_text("✅ Your reply has been sent anonymously.")
                return

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.route("/startbot")
def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(application.run_polling())
    return "Bot started via polling."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

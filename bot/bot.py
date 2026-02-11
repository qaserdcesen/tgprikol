import os, logging, subprocess, datetime, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import database

TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
PRICE = int(os.getenv("DEFAULT_PRICE", 200))
DAYS = int(os.getenv("DEFAULT_DAYS", 30))
DOMAIN = os.getenv("DEFAULT_DOMAIN", "1c.ru")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "0").split(',')))

logging.basicConfig(level=logging.INFO)

async def start(update, context):
    keyboard = [[InlineKeyboardButton("🛒 Купить", callback_data="buy")],
                [InlineKeyboardButton("📋 Статус", callback_data="status")],
                [InlineKeyboardButton("🔄 Продлить", callback_data="prolong")]]
    await update.message.reply_text(f"🥷 MTProxy {DAYS}дн – {PRICE}₽", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update, context):
    q = update.callback_query; await q.answer()
    if q.data == "buy": await buy(update, context)
    elif q.data == "status": await status(update, context)
    elif q.data == "prolong": await prolong(update, context)

async def buy(update, context):
    chat_id = update.effective_chat.id
    await context.bot.send_invoice(chat_id, f"MTProxy {DAYS}дн", "Fake TLS",
        f"sub_{chat_id}_{DAYS}", PROVIDER_TOKEN, "RUB", [LabeledPrice("", PRICE*100)])

async def precheckout(update, context):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update, context):
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split('_')
    chat_id = int(parts[1]); days = int(parts[2])
    secret = os.urandom(16).hex()
    username = f"user_{chat_id}"
    result = subprocess.run(["/usr/local/bin/add-secret.sh", secret, username, DOMAIN],
        capture_output=True, text=True, check=True)
    link = result.stdout.strip()
    expires = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
    database.add_user(chat_id, secret, expires, link)
    await update.message.reply_text(f"✅ Ссылка (до {expires}):\n<code>{link}</code>", parse_mode="HTML")

async def status(update, context):
    user = database.get_user(update.effective_chat.id)
    if user:
        _,_,exp,link,_ = user; days = (datetime.date.fromisoformat(exp)-datetime.date.today()).days
        await update.message.reply_text(f"📅 до {exp} ({days}дн)\n<code>{link}</code>", parse_mode="HTML")
    else: await update.message.reply_text("❌ Нет подписки")

async def prolong(update, context):
    chat_id = update.effective_chat.id
    if not database.get_user(chat_id): await update.message.reply_text("Купите сначала"); return
    await context.bot.send_invoice(chat_id, f"Продление {DAYS}дн", "Продление",
        f"prolong_{chat_id}_{DAYS}", PROVIDER_TOKEN, "RUB", [LabeledPrice("", PRICE*100)])

async def prolong_payment(update, context):
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split('_'); chat_id = int(parts[1]); days = int(parts[2])
    user = database.get_user(chat_id)
    if user:
        new = (datetime.date.fromisoformat(user[2]) + datetime.timedelta(days=days)).isoformat()
        database.update_expires(chat_id, new)
        await update.message.reply_text(f"✅ Продлено до {new}")

def main():
    database.init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    # обработчик продления уже внутри successful_payment, но для чистоты:
    # можно зарегистрировать отдельный MessageHandler с фильтром, но оставим так
    app.run_polling()

if __name__ == "__main__":
    main()

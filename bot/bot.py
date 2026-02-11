import os
import logging
import subprocess
import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    CommandHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
import database


TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
PRICE = int(os.getenv("DEFAULT_PRICE", 200))
DAYS = int(os.getenv("DEFAULT_DAYS", 30))
DOMAIN = os.getenv("DEFAULT_DOMAIN", "1c.ru")
ADMIN_IDS = list(
    map(int, filter(None, os.getenv("ADMIN_IDS", "").split(",")))
)  # зарезервировано под админ-команды

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)


def _require_env():
    missing = [name for name in ("BOT_TOKEN", "PROVIDER_TOKEN") if not os.getenv(name)]
    if missing:
        raise SystemExit(
            f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}"
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛒 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton("📋 Мой статус", callback_data="status")],
        [InlineKeyboardButton("🔄 Продлить", callback_data="prolong")],
    ]
    await update.message.reply_text(
        (
            "👋 Привет! Это бот для покупки MTProto прокси.\n"
            f"💰 {PRICE}₽ / {DAYS} дней\n"
            f"🔒 Fake TLS маскировка под {DOMAIN}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy":
        await buy(update, context)
    elif query.data == "status":
        await status(update, context)
    elif query.data == "prolong":
        await prolong(update, context)


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id

    await context.bot.send_invoice(
        chat_id,
        title=f"MTProxy {DAYS} дней",
        description=f"Приватный прокси с Fake TLS. Домен: {DOMAIN}",
        payload=f"sub_{chat_id}_{DAYS}",
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(f"Подписка {DAYS} дней", PRICE * 100)],
    )


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split("_")
    chat_id = int(parts[1])
    days = int(parts[2])

    secret = os.urandom(16).hex()
    username = f"user_{chat_id}"

    try:
        result = subprocess.run(
            ["/usr/local/bin/add-secret.sh", secret, username, DOMAIN],
            capture_output=True,
            text=True,
            check=True,
        )
        link = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Add secret failed: {e.stderr}")
        await update.message.reply_text(
            "❌ Ошибка создания прокси. Администратор уведомлен."
        )
        return

    expires = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
    database.add_user(chat_id, secret, expires, link)

    keyboard = [[InlineKeyboardButton("📋 Статус", callback_data="status")]]
    await update.message.reply_text(
        (
            "✔ Оплата прошла!\n"
            f"⌛ Действует до: {expires}\n"
            f"🔗 <code>{link}</code>"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    user = database.get_user(chat_id)

    if user:
        _, _, expires, link, _ = user
        days_left = (datetime.date.fromisoformat(expires) - datetime.date.today()).days
        await query.message.reply_text(
            (
                f"⌛ Истекает: {expires} (осталось {days_left} дн.)\n"
                f"🔗 <code>{link}</code>"
            ),
            parse_mode="HTML",
        )
    else:
        await query.message.reply_text("❌ У вас нет активной подписки.")


async def prolong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id

    if not database.get_user(chat_id):
        await query.message.reply_text("❌ Сначала купите подписку через 🛒")
        return

    await context.bot.send_invoice(
        chat_id,
        title=f"Продление {DAYS} дней",
        description="Продление подписки. Ссылка останется той же.",
        payload=f"prolong_{chat_id}_{DAYS}",
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(f"Продление {DAYS} дней", PRICE * 100)],
    )


async def prolong_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split("_")
    chat_id = int(parts[1])
    days = int(parts[2])

    user = database.get_user(chat_id)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден")
        return

    new_expires = (
        datetime.date.fromisoformat(user[2]) + datetime.timedelta(days=days)
    ).isoformat()
    database.update_expires(chat_id, new_expires)

    await update.message.reply_text(
        (
            f"✔ Подписка продлена до {new_expires}\n"
            f"🔗 Ссылка осталась прежней: <code>{user[3]}</code>"
        ),
        parse_mode="HTML",
    )


async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    targets = [
        (today, "⏳ Сегодня истекает ваша подписка. Чтобы не потерять доступ, продлите её через кнопку «Продлить»."),
        (
            today + datetime.timedelta(days=1),
            "🕐 Завтра истекает ваша подписка. Нажмите «Продлить», чтобы сохранить доступ.",
        ),
    ]

    for target_date, message in targets:
        users = database.get_users_by_date(target_date.isoformat())
        for user in users:
            chat_id = user[0]
            try:
                await context.bot.send_message(chat_id, message)
            except Exception as e:
                logging.warning(f"Reminder send failed for {chat_id}: {e}")


def main():
    _require_env()
    database.init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(PreCheckoutQueryHandler(precheckout))

    # Обработчик платежей (и покупка, и продление)
    async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        payload = update.message.successful_payment.invoice_payload
        if payload.startswith("sub_"):
            await successful_payment(update, context)
        elif payload.startswith("prolong_"):
            await prolong_payment(update, context)

    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_handler))

    # Ежедневные напоминания об истечении подписки (UTC 06:00)
    app.job_queue.run_daily(
        send_reminders,
        time=datetime.time(hour=6, minute=0, tzinfo=datetime.timezone.utc),
        name="reminders",
    )

    app.run_polling()


if __name__ == "__main__":
    main()

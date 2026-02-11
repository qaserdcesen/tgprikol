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
WAITING_OP = {}  # chat_id -> admin action

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
    elif query.data.startswith("buy_"):
        await buy_specific(update, context)
    elif query.data == "status":
        await status(update, context)
    elif query.data == "prolong":
        await prolong(update, context)


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    options = [
        InlineKeyboardButton("💳 30 дней", callback_data="buy_30"),
        InlineKeyboardButton("💳 60 дней", callback_data="buy_60"),
        InlineKeyboardButton("💳 90 дней", callback_data="buy_90"),
    ]
    await query.message.reply_text(
        "Выберите срок подписки:",
        reply_markup=InlineKeyboardMarkup([options]),
    )


def _price_for(days: int) -> int:
    # Линейная цена от базового тарифа (PRICE за DAYS)
    return int(round(PRICE * days / DAYS))


async def buy_specific(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    try:
        days = int(query.data.split("_")[1])
    except Exception:
        await query.message.reply_text("Не понял срок подписки.")
        return

    await context.bot.send_invoice(
        chat_id,
        title=f"MTProxy {days} дней",
        description=f"Приватный прокси с Fake TLS. Домен: {DOMAIN}",
        payload=f"sub_{chat_id}_{days}",
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(f"Подписка {days} дней", _price_for(days) * 100)],
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


def _is_admin(chat_id: int) -> bool:
    return chat_id in ADMIN_IDS


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not _is_admin(chat_id):
        await update.message.reply_text("🚫 Нет прав.")
        return

    keyboard = [
        [
            InlineKeyboardButton("📜 Логи", callback_data="admin_logs"),
            InlineKeyboardButton("➕ Создать секрет", callback_data="admin_create"),
        ],
        [InlineKeyboardButton("🗑 Удалить пользователя", callback_data="admin_delete")],
        [InlineKeyboardButton("👥 Все пользователи", callback_data="admin_list")],
    ]
    await update.message.reply_text(
        "Админ-панель:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    if not _is_admin(chat_id):
        await query.message.reply_text("🚫 Нет прав.")
        return

    data = query.data
    if data == "admin_logs":
        await _send_logs(chat_id, context)
    elif data == "admin_create":
        WAITING_OP[chat_id] = "create"
        await query.message.reply_text(
            "Отправь сообщением: <telegram_id> <дней>. Пример: 123456789 30\n"
            "Если дней не указать, возьмётся DEFAULT_DAYS."
        )
    elif data == "admin_delete":
        WAITING_OP[chat_id] = "delete"
        await query.message.reply_text("Отправь telegram_id пользователя для удаления.")
    elif data == "admin_list":
        await _send_user_list(chat_id, context)


async def _send_logs(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", "50", "telemt-bot"],
            capture_output=True,
            text=True,
            check=True,
        )
        text = result.stdout or result.stderr or "Логи пусты."
    except subprocess.CalledProcessError as e:
        text = f"Не удалось получить логи: {e.stderr or e}"

    if len(text) > 3800:  # лимит телеги 4096
        text = "…(обрезано)\n" + text[-3800:]
    await context.bot.send_message(chat_id, f"<code>{text}</code>", parse_mode="HTML")


async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in WAITING_OP:
        return

    op = WAITING_OP.pop(chat_id)

    if op == "create":
        parts = update.message.text.strip().split()
        if not parts:
            await update.message.reply_text("Формат: <telegram_id> <дней (опц.)>")
            return
        try:
            target_id = int(parts[0])
            days = int(parts[1]) if len(parts) > 1 else DAYS
        except ValueError:
            await update.message.reply_text("Нужны числа: <telegram_id> <дней>")
            return

        secret = os.urandom(16).hex()
        username = f"user_{target_id}"
        try:
            result = subprocess.run(
                ["/usr/local/bin/add-secret.sh", secret, username, DOMAIN],
                capture_output=True,
                text=True,
                check=True,
            )
            link = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.error(f"Admin add secret failed: {e.stderr}")
            await update.message.reply_text("❌ Не удалось создать секрет.")
            return

        expires = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
        database.add_user(target_id, secret, expires, link)
        await update.message.reply_text(
            f"✅ Создано для {target_id}\nИстекает: {expires}\n🔗 <code>{link}</code>",
            parse_mode="HTML",
        )

    elif op == "delete":
        try:
            target_id = int(update.message.text.strip())
        except ValueError:
            await update.message.reply_text("Нужно число — telegram_id.")
            return

        username = f"user_{target_id}"
        try:
            subprocess.run(
                ["/usr/local/bin/remove-secret.sh", username],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logging.error(f"Admin remove secret failed: {e.stderr}")
            await update.message.reply_text("❌ Не удалось удалить секрет в конфиге.")
            return

        database.delete_user(target_id)
        await update.message.reply_text(f"🗑 Пользователь {target_id} удалён.")


async def _send_user_list(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_users()
    if not users:
        await context.bot.send_message(chat_id, "Пользователей нет.")
        return

    lines = []
    for tid, secret, expires, _link in users:
        lines.append(f"{tid} | истекает {expires} | {secret}")

    text = "\n".join(lines)
    if len(text) > 3800:
        text = "…(обрезано)\n" + text[-3800:]
    await context.bot.send_message(chat_id, f"<code>{text}</code>", parse_mode="HTML")


def main():
    _require_env()
    database.init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(buy(_\\d+)?|status|prolong)$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout))

    # Обработчик платежей (и покупка, и продление)
    async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        payload = update.message.successful_payment.invoice_payload
        if payload.startswith("sub_"):
            await successful_payment(update, context)
        elif payload.startswith("prolong_"):
            await prolong_payment(update, context)

    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_handler))
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(ADMIN_IDS), admin_text))

    # Ежедневные напоминания об истечении подписки (UTC 06:00)
    app.job_queue.run_daily(
        send_reminders,
        time=datetime.time(hour=6, minute=0, tzinfo=datetime.timezone.utc),
        name="reminders",
    )

    app.run_polling()


if __name__ == "__main__":
    main()

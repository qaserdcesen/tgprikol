#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
)  # Р·Р°СЂРµР·РµСЂРІРёСЂРѕРІР°РЅРѕ РїРѕРґ Р°РґРјРёРЅ-РєРѕРјР°РЅРґС‹
WAITING_OP = {}  # chat_id -> admin action

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)


def _require_env():
    missing = [name for name in ("BOT_TOKEN", "PROVIDER_TOKEN") if not os.getenv(name)]
    if missing:
        raise SystemExit(
            f"РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ: {', '.join(missing)}"
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("рџ›’ РљСѓРїРёС‚СЊ РїРѕРґРїРёСЃРєСѓ", callback_data="buy")],
        [InlineKeyboardButton("рџ“‹ РњРѕР№ СЃС‚Р°С‚СѓСЃ", callback_data="status")],
        [InlineKeyboardButton("рџ”„ РџСЂРѕРґР»РёС‚СЊ", callback_data="prolong")],
    ]
    await update.message.reply_text(
        (
            "рџ‘‹ РџСЂРёРІРµС‚! Р­С‚Рѕ Р±РѕС‚ РґР»СЏ РїРѕРєСѓРїРєРё MTProto РїСЂРѕРєСЃРё.\n"
            f"рџ’° {PRICE}в‚Ѕ / {DAYS} РґРЅРµР№\n"
            f"рџ”’ Fake TLS РјР°СЃРєРёСЂРѕРІРєР° РїРѕРґ {DOMAIN}"
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
        InlineKeyboardButton("рџ’і 30 РґРЅРµР№", callback_data="buy_30"),
        InlineKeyboardButton("рџ’і 60 РґРЅРµР№", callback_data="buy_60"),
        InlineKeyboardButton("рџ’і 90 РґРЅРµР№", callback_data="buy_90"),
    ]
    await query.message.reply_text(
        "Р’С‹Р±РµСЂРёС‚Рµ СЃСЂРѕРє РїРѕРґРїРёСЃРєРё:",
        reply_markup=InlineKeyboardMarkup([options]),
    )


def _price_for(days: int) -> int:
    # Р›РёРЅРµР№РЅР°СЏ С†РµРЅР° РѕС‚ Р±Р°Р·РѕРІРѕРіРѕ С‚Р°СЂРёС„Р° (PRICE Р·Р° DAYS)
    return int(round(PRICE * days / DAYS))


async def buy_specific(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    try:
        days = int(query.data.split("_")[1])
    except Exception:
        await query.message.reply_text("РќРµ РїРѕРЅСЏР» СЃСЂРѕРє РїРѕРґРїРёСЃРєРё.")
        return

    await context.bot.send_invoice(
        chat_id,
        title=f"MTProxy {days} РґРЅРµР№",
        description=f"РџСЂРёРІР°С‚РЅС‹Р№ РїСЂРѕРєСЃРё СЃ Fake TLS. Р”РѕРјРµРЅ: {DOMAIN}",
        payload=f"sub_{chat_id}_{days}",
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(f"РџРѕРґРїРёСЃРєР° {days} РґРЅРµР№", _price_for(days) * 100)],
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
            "вќЊ РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ РїСЂРѕРєСЃРё. РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СѓРІРµРґРѕРјР»РµРЅ."
        )
        return

    expires = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
    database.add_user(chat_id, secret, expires, link)

    keyboard = [
        [InlineKeyboardButton("Статус", callback_data="status")],
        [InlineKeyboardButton("Открыть прокси", url=link)],
    ]
    await update.message.reply_text(
        (
            "вњ” РћРїР»Р°С‚Р° РїСЂРѕС€Р»Р°!\n"
            f"вЊ› Р”РµР№СЃС‚РІСѓРµС‚ РґРѕ: {expires}"
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
        keyboard = [[InlineKeyboardButton("Открыть прокси", url=link)]]
        await query.message.reply_text(
            f"? Истекает: {expires} (осталось {days_left} дн.)",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await query.message.reply_text("вќЊ РЈ РІР°СЃ РЅРµС‚ Р°РєС‚РёРІРЅРѕР№ РїРѕРґРїРёСЃРєРё.")


async def prolong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id

    if not database.get_user(chat_id):
        await query.message.reply_text("вќЊ РЎРЅР°С‡Р°Р»Р° РєСѓРїРёС‚Рµ РїРѕРґРїРёСЃРєСѓ С‡РµСЂРµР· рџ›’")
        return

    await context.bot.send_invoice(
        chat_id,
        title=f"РџСЂРѕРґР»РµРЅРёРµ {DAYS} РґРЅРµР№",
        description="РџСЂРѕРґР»РµРЅРёРµ РїРѕРґРїРёСЃРєРё. РЎСЃС‹Р»РєР° РѕСЃС‚Р°РЅРµС‚СЃСЏ С‚РѕР№ Р¶Рµ.",
        payload=f"prolong_{chat_id}_{DAYS}",
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(f"РџСЂРѕРґР»РµРЅРёРµ {DAYS} РґРЅРµР№", PRICE * 100)],
    )


async def prolong_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split("_")
    chat_id = int(parts[1])
    days = int(parts[2])

    user = database.get_user(chat_id)
    if not user:
        await update.message.reply_text("вќЊ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ")
        return

    new_expires = (
        datetime.date.fromisoformat(user[2]) + datetime.timedelta(days=days)
    ).isoformat()
    database.update_expires(chat_id, new_expires)

    keyboard = [[InlineKeyboardButton("Открыть прокси", url=user[3])]]
    await update.message.reply_text(
        f"вњ” РџРѕРґРїРёСЃРєР° РїСЂРѕРґР»РµРЅР° РґРѕ {new_expires}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    targets = [
        (today, "вЏі РЎРµРіРѕРґРЅСЏ РёСЃС‚РµРєР°РµС‚ РІР°С€Р° РїРѕРґРїРёСЃРєР°. Р§С‚РѕР±С‹ РЅРµ РїРѕС‚РµСЂСЏС‚СЊ РґРѕСЃС‚СѓРї, РїСЂРѕРґР»РёС‚Рµ РµС‘ С‡РµСЂРµР· РєРЅРѕРїРєСѓ В«РџСЂРѕРґР»РёС‚СЊВ»."),
        (
            today + datetime.timedelta(days=1),
            "рџ•ђ Р—Р°РІС‚СЂР° РёСЃС‚РµРєР°РµС‚ РІР°С€Р° РїРѕРґРїРёСЃРєР°. РќР°Р¶РјРёС‚Рµ В«РџСЂРѕРґР»РёС‚СЊВ», С‡С‚РѕР±С‹ СЃРѕС…СЂР°РЅРёС‚СЊ РґРѕСЃС‚СѓРї.",
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
        await update.message.reply_text("рџљ« РќРµС‚ РїСЂР°РІ.")
        return

    keyboard = [
        [
            InlineKeyboardButton("рџ“њ Р›РѕРіРё", callback_data="admin_logs"),
            InlineKeyboardButton("вћ• РЎРѕР·РґР°С‚СЊ СЃРµРєСЂРµС‚", callback_data="admin_create"),
        ],
        [InlineKeyboardButton("рџ—‘ РЈРґР°Р»РёС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ", callback_data="admin_delete")],
        [InlineKeyboardButton("рџ‘Ґ Р’СЃРµ РїРѕР»СЊР·РѕРІР°С‚РµР»Рё", callback_data="admin_list")],
    ]
    await update.message.reply_text(
        "РђРґРјРёРЅ-РїР°РЅРµР»СЊ:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    if not _is_admin(chat_id):
        await query.message.reply_text("рџљ« РќРµС‚ РїСЂР°РІ.")
        return

    data = query.data
    if data == "admin_logs":
        await _send_logs(chat_id, context)
    elif data == "admin_create":
        WAITING_OP[chat_id] = "create"
        await query.message.reply_text(
            "РћС‚РїСЂР°РІСЊ СЃРѕРѕР±С‰РµРЅРёРµРј: <telegram_id> <РґРЅРµР№>. РџСЂРёРјРµСЂ: 123456789 30\n"
            "Р•СЃР»Рё РґРЅРµР№ РЅРµ СѓРєР°Р·Р°С‚СЊ, РІРѕР·СЊРјС‘С‚СЃСЏ DEFAULT_DAYS."
        )
    elif data == "admin_delete":
        WAITING_OP[chat_id] = "delete"
        await query.message.reply_text("РћС‚РїСЂР°РІСЊ telegram_id РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РґР»СЏ СѓРґР°Р»РµРЅРёСЏ.")
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
        text = result.stdout or result.stderr or "Р›РѕРіРё РїСѓСЃС‚С‹."
    except subprocess.CalledProcessError as e:
        text = f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ Р»РѕРіРё: {e.stderr or e}"

    if len(text) > 3800:  # Р»РёРјРёС‚ С‚РµР»РµРіРё 4096
        text = "вЂ¦(РѕР±СЂРµР·Р°РЅРѕ)\n" + text[-3800:]
    await context.bot.send_message(chat_id, f"<code>{text}</code>", parse_mode="HTML")


async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in WAITING_OP:
        return

    op = WAITING_OP.pop(chat_id)

    if op == "create":
        parts = update.message.text.strip().split()
        if not parts:
            await update.message.reply_text("Р¤РѕСЂРјР°С‚: <telegram_id> <РґРЅРµР№ (РѕРїС†.)>")
            return
        try:
            target_id = int(parts[0])
            days = int(parts[1]) if len(parts) > 1 else DAYS
        except ValueError:
            await update.message.reply_text("РќСѓР¶РЅС‹ С‡РёСЃР»Р°: <telegram_id> <РґРЅРµР№>")
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
            await update.message.reply_text("вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ СЃРµРєСЂРµС‚.")
            return

        expires = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
        database.add_user(target_id, secret, expires, link)
        keyboard = [[InlineKeyboardButton("Открыть прокси", url=link)]]
        await update.message.reply_text(
            f"вњ… РЎРѕР·РґР°РЅРѕ РґР»СЏ {target_id}\nРСЃС‚РµРєР°РµС‚: {expires}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif op == "delete":
        try:
            target_id = int(update.message.text.strip())
        except ValueError:
            await update.message.reply_text("РќСѓР¶РЅРѕ С‡РёСЃР»Рѕ вЂ” telegram_id.")
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
            await update.message.reply_text("вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ СЃРµРєСЂРµС‚ РІ РєРѕРЅС„РёРіРµ.")
            return

        database.delete_user(target_id)
        await update.message.reply_text(f"рџ—‘ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ {target_id} СѓРґР°Р»С‘РЅ.")


async def _send_user_list(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    users = database.get_all_users()
    if not users:
        await context.bot.send_message(chat_id, "РџРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РЅРµС‚.")
        return

    lines = []
    for tid, secret, expires, _link in users:
        lines.append(f"{tid} | РёСЃС‚РµРєР°РµС‚ {expires} | {secret}")

    text = "\n".join(lines)
    if len(text) > 3800:
        text = "вЂ¦(РѕР±СЂРµР·Р°РЅРѕ)\n" + text[-3800:]
    await context.bot.send_message(chat_id, f"<code>{text}</code>", parse_mode="HTML")


def main():
    _require_env()
    database.init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(buy(_\\d+)?|status|prolong)$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout))

    # РћР±СЂР°Р±РѕС‚С‡РёРє РїР»Р°С‚РµР¶РµР№ (Рё РїРѕРєСѓРїРєР°, Рё РїСЂРѕРґР»РµРЅРёРµ)
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

    # Р•Р¶РµРґРЅРµРІРЅС‹Рµ РЅР°РїРѕРјРёРЅР°РЅРёСЏ РѕР± РёСЃС‚РµС‡РµРЅРёРё РїРѕРґРїРёСЃРєРё (UTC 06:00)
    app.job_queue.run_daily(
        send_reminders,
        time=datetime.time(hour=6, minute=0, tzinfo=datetime.timezone.utc),
        name="reminders",
    )

    app.run_polling()


if __name__ == "__main__":
    main()

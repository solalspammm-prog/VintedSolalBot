
import os
import json
from datetime import time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

MAX_PRICE = 20
MIN_MARGIN = 10
DB = "deals.json"

PHOTO, TITLE, BUY, RESALE = range(4)


def authorized(update):
    return update.effective_user.id == OWNER_ID


def load_deals():
    try:
        with open(DB, "r", encoding="utf-8") as f:
            return json.load(f).get("deals", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_deals(deals):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump({"deals": deals}, f, ensure_ascii=False, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    await update.message.reply_text(
        "Bienvenue sur VintedSolalBot !\n\n"
        "Envoie-moi directement une photo d'un article "
        "pour analyser sa rentabilité.\n\n"
        "/list : voir tes articles\n"
        "/daily : recevoir ton bilan\n"
        "/cancel : annuler une analyse"
    )


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return ConversationHandler.END

    context.user_data["photo_id"] = update.message.photo[-1].file_id

    await update.message.reply_text("Quel est le nom de cet article ?")
    return TITLE


async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text.strip()

    await update.message.reply_text("Quel est son prix d'achat en euros ?")
    return BUY


async def get_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        buy = float(update.message.text.replace(",", "."))
        if buy < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Entre un prix valide.")
        return BUY

    context.user_data["buy"] = buy

    await update.message.reply_text(
        "À combien penses-tu pouvoir le revendre ?"
    )
    return RESALE


async def get_resale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resale = float(update.message.text.replace(",", "."))
        if resale < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Entre un prix valide.")
        return RESALE

    buy = context.user_data["buy"]
    title = context.user_data["title"]
    margin = resale - buy

    deal = {
        "title": title,
        "buy": buy,
        "resale": resale,
        "margin": margin,
        "photo_id": context.user_data["photo_id"]
    }

    deals = load_deals()
    deals.append(deal)
    save_deals(deals)

    if buy <= MAX_PRICE and margin >= MIN_MARGIN:
        status = "OPPORTUNITÉ À EXAMINER"
    else:
        status = "SOUS TES CRITÈRES"

    await update.message.reply_text(
        f"Analyse terminée !\n\n"
        f"Article : {title}\n"
        f"Achat : {buy:.2f} €\n"
        f"Revente estimée : {resale:.2f} €\n"
        f"Marge brute : {margin:.2f} €\n\n"
        f"{status}\n\n"
        "Article enregistré dans ton historique."
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Analyse annulée.")
    return ConversationHandler.END


async def listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    deals = load_deals()

    if not deals:
        await update.message.reply_text("Aucun article enregistré.")
        return

    for deal in deals:
        await update.message.reply_text(
            f"{deal['title']}\n"
            f"Achat : {deal['buy']:.2f} €\n"
            f"Marge brute : {deal['resale'] - deal['buy']:.2f} €"
        )


async def daily(context: ContextTypes.DEFAULT_TYPE):
    deals = load_deals()

    selected = [
        d for d in deals
        if d["buy"] <= MAX_PRICE
        and d["resale"] - d["buy"] >= MIN_MARGIN
    ]

    message = "BILAN QUOTIDIEN - VintedSolalBot\n\n"

    if not selected:
        message += "Aucune opportunité ne respecte tes critères."
    else:
        for d in selected:
            message += (
                f"{d['title']}\n"
                f"Achat : {d['buy']:.2f} €\n"
                f"Revente : {d['resale']:.2f} €\n"
                f"Marge brute : {d['resale'] - d['buy']:.2f} €\n\n"
            )

    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=message
    )


async def daily_command(update, context):
    if authorized(update):
        await daily(context)


async def main():
    app = Application.builder().token(TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO, receive_photo),
            CommandHandler("add", lambda u, c: receive_photo(u, c))
        ],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            BUY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_buy)],
            RESALE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_resale)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conversation)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", listing))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("cancel", cancel))

    app.job_queue.run_daily(
        daily,
        time=time(19, 0, tzinfo=ZoneInfo("Europe/Paris"))
    )

    print("VintedSolalBot démarré !")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.wait_for_stop()
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


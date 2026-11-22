
import os
import json
from datetime import time
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

MAX_PRICE = 20
MIN_MARGIN = 10
DB = "deals.json"

CATEGORIES = [
    "Sweats et vestes",
    "Maillots de football",
    "Chaussures",
    "Survetements",
    "Jeux video",
    "Accessoires"
]

def load_deals():
    try:
        with open(DB, "r", encoding="utf-8") as f:
            return json.load(f)["deals"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return []

def save_deals(deals):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump({"deals": deals}, f, ensure_ascii=False, indent=2)

def authorized(update):
    return update.effective_chat.id == OWNER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(
        "Bienvenue sur VintedSolalBot !\n\n"
        "/add - Ajouter une annonce\n"
        "/list - Voir les annonces\n"
        "/daily - Faire le bilan"
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) != 5:
        await update.message.reply_text(
            "Format :\n"
            "/add categorie | titre | achat | revente | lien"
        )
        return

    category, title, buy, resale, url = parts

    if category.lower() not in [c.lower() for c in CATEGORIES]:
        await update.message.reply_text("Catégorie inconnue.")
        return

    try:
        buy = float(buy.replace(",", "."))
        resale = float(resale.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Prix invalides.")
        return

    if buy < 0 or resale < 0:
        await update.message.reply_text("Prix invalides.")
        return

    deals = load_deals()
    deals.append({
        "category": category,
        "title": title,
        "buy": buy,
        "resale": resale,
        "url": url
    })
    save_deals(deals)

    margin = resale - buy
    status = (
        "OPPORTUNITÉ À EXAMINER"
        if buy <= MAX_PRICE and margin >= MIN_MARGIN
        else "Sous tes critères"
    )

    await update.message.reply_text(
        f"{title}\n"
        f"Achat : {buy:.2f} €\n"
        f"Revente estimée : {resale:.2f} €\n"
        f"Marge brute : {margin:.2f} €\n"
        f"{status}"
    )

async def listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    deals = load_deals()

    if not deals:
        await update.message.reply_text("Aucune annonce enregistrée.")
        return

    for deal in deals:
        margin = deal["resale"] - deal["buy"]
        await update.message.reply_text(
            f"{deal['title']}\n"
            f"Achat : {deal['buy']:.2f} €\n"
            f"Marge brute : {margin:.2f} €\n"
            f"{deal['url']}"
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
        message += "Aucune opportunité enregistrée ne respecte tes critères."
    else:
        for d in selected:
            margin = d["resale"] - d["buy"]
            message += (
                f"{d['title']}\n"
                f"Achat : {d['buy']:.2f} €\n"
                f"Marge brute : {margin:.2f} €\n"
                f"{d['url']}\n\n"
            )

    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=message
    )

async def daily_command(update, context):
    if authorized(update):
        await daily(context)

async def help_command(update, context):
    if authorized(update):
        await update.message.reply_text(
            "/add categorie | titre | achat | revente | lien\n"
            "/list\n"
            "/daily"
        )

def main():
    load_deals()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", listing))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("help", help_command))

    app.job_queue.run_daily(
        daily,
        time=time(19, 0, tzinfo=ZoneInfo("Europe/Paris"))
    )

    print("VintedSolalBot démarré !")
    app.run_polling()

if __name__ == "__main__":
    main()

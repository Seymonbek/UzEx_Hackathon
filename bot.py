"""Professional Telegram-bot: UZEX AI Hackathon 2026.
Barcha xususiyatlar: Inline Asos/SQL tugmasi, statistika, namunaviy tugmalar, ko'p tillilik.

Запуск:
    python bot.py
"""
import os, re, html, asyncio, logging, sys
sys.stdout.reconfigure(encoding="utf-8")
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import boot
boot.ensure_db()
import agent
import datastore as ds

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("uzex_bot")

HELLO = (
    "🇺🇿 <b>Assalomu alaykum! Men UZEX birja bitimlari AI-agentiman.</b>\n\n"
    "Men O'zbekiston Respublika tovar-xom ashyo birjasining <b>500 000 ta</b> bitimdan iborat reyestri (2022–2026) "
    "bo'yicha o'zbek va rus tillaridagi savollaringizga <b>faqat ma'lumotlar asosida</b> aniq javob beraman.\n\n"
    "🇷🇺 <i>Здравствуйте! Я аналитический агент биржи UZEX (500 000 сделок, 2022–2026). "
    "Отвечаю точно и только по данным реестра.</i>\n\n"
    "📌 <b>Asosiy buyruqlar / Команды:</b>\n"
    "• /sql — Oxirgi javobning hisoblash asosi (SQL)\n"
    "• /stat — Ma'lumotlar bazasi va tizim holati\n"
    "• /clear — Suhbat tarixini tozalash\n"
    "• /help — Yordam va ko'rsatmalar\n\n"
    "<i>Quyidagi namunaviy savollardan birini tanlang yoki o'z savolingizni yozing:</i>"
)

SAMPLE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("2024-yilda nechta bitim tuzilgan va summasi qancha?")],
        [KeyboardButton("Какой товар принёс наибольшую сумму в 2025 году?")],
        [KeyboardButton("Eng ko'p xarid qilgan kompaniya kim (STIR bilan)?")],
        [KeyboardButton("2026-yilda eksport bitimlari hajmi va dollar summasi?")]
    ],
    resize_keyboard=True
)

_last_traces = {}


def format_tg_html(text: str) -> str:
    """Format markdown bold **text** to HTML <b>text</b> and escape XML chars."""
    escaped = html.escape(text)
    # replace **bold** with <b>bold</b>
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped


async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELLO, parse_mode=ParseMode.HTML, reply_markup=SAMPLE_KEYBOARD)


async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "💡 <b>UZEX AI-Agent haqida:</b>\n\n"
        "• <b>Hech qanday gallyutsinatsiya yo'q:</b> Agent raqamlarni to'qimaydi, har bir son SQLite bazasidagi SQL so'rovi orqali olinadi.\n"
        "• <b>Ma'lumot yo'q bo'lsa:</b> Agent buni ochiq aytadi (masalan, 2027-yilgi bitimlar yoki reyestrda yo'q tovarlar so'ralsa).\n"
        "• <b>Asos ko'rinadi:</b> Har bir javob ostidagi <b>'🔍 Asos (SQL)'</b> tugmasi orqali hisoblash kodi va manbani tekshirishingiz mumkin.\n"
        "• <b>Tillarni tushunish:</b> Rus va o'zbek tillarini (ham kirill, ham lotin) to'liq tushunadi."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def stat_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ov = ds.db_overview()
    prov = agent.get_active_provider()
    keys_count = getattr(agent, f"{prov}_pool").count() if hasattr(agent, f"{prov}_pool") else 1
    stat_text = (
        f"📊 <b>Baza va Tizim Statistikasi:</b>\n\n"
        f"• <b>Jami bitimlar:</b> {ov.get('deals', 500000):,} ta\n"
        f"• <b>Qamrov davri:</b> {ov.get('first_date')} — {ov.get('last_date')}\n"
        f"• <b>Ma'lumotlar bazasi:</b> SQLite (uzex.db, ~392 MB, Indekslangan)\n"
        f"• <b>AI Provayder:</b> {prov.upper()} ({agent.MODEL})\n"
        f"• <b>Faol API kalitlar zaxirasi (Pool):</b> {keys_count} ta\n"
        f"• <b>Xavfsizlik:</b> Read-Only (SQLITE_SELECT only, C-level)"
    )
    await update.message.reply_text(stat_text, parse_mode=ParseMode.HTML)


async def clear_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ctx.chat_data["h"] = []
    if chat_id in _last_traces:
        del _last_traces[chat_id]
    await update.message.reply_text("🧹 <b>Suhbat tarixi tozalandi.</b> Yangi savolingizni berishingiz mumkin.", parse_mode=ParseMode.HTML)


async def show_sql_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    tr = _last_traces.get(chat_id, {}).get("trace")
    if not tr:
        return await update.message.reply_text("Hali savol berilmadi yoki SQL asosi mavjud emas.")
    
    basis_parts = []
    for t in tr:
        tool_name = t.get("tool", "")
        tool_input = t.get("input", {})
        tool_out = t.get("output", {})
        query = tool_input.get("query") or str(tool_input)
        out_summary = f"Qatorlar: {tool_out.get('row_count')}" if isinstance(tool_out, dict) and "row_count" in tool_out else ""
        basis_parts.append(f"<b>[{tool_name}]</b>\n<code>{html.escape(query)}</code>\n<i>{out_summary}</i>")

    txt = "\n\n".join(basis_parts)
    await update.message.reply_text(f"🔍 <b>Hisoblash asosi (SQL):</b>\n\n{txt[:4000]}", parse_mode=ParseMode.HTML)


async def inline_button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    
    if query.data == "view_sql":
        tr = _last_traces.get(chat_id, {}).get("trace")
        if not tr:
            return await query.message.reply_text("SQL asosi topilmadi.")
        
        basis_parts = []
        for t in tr:
            tool_name = t.get("tool", "")
            tool_input = t.get("input", {})
            tool_out = t.get("output", {})
            q_text = tool_input.get("query") or str(tool_input)
            rows_cnt = tool_out.get("row_count", 0) if isinstance(tool_out, dict) else 0
            basis_parts.append(f"<b>[{tool_name}]</b>\n<code>{html.escape(q_text)}</code>\n➜ Qatorlar soni: <b>{rows_cnt}</b>")

        msg_body = "\n\n".join(basis_parts)
        await query.message.reply_text(
            f"🔍 <b>Hisoblash asosi va bajarilgan SQL:</b>\n\n{msg_body[:4000]}",
            parse_mode=ParseMode.HTML
        )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    if not text:
        return

    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)
    hist = ctx.chat_data.setdefault("h", [])

    try:
        res = await asyncio.to_thread(agent.ask, text[:2000], hist)
    except Exception as e:
        logger.exception("Agent execution failed")
        err_msg = str(e)
        if "API_KEY" in err_msg or "не задан" in err_msg:
            return await update.message.reply_text("⚠️ <b>Xatolik:</b> API kalit kiritilmagan. Iltimos, .env fayliga GEMINI_API_KEYS ni kiriting.", parse_mode=ParseMode.HTML)
        return await update.message.reply_text(f"⚠️ <b>Xatolik yuz berdi:</b> {html.escape(err_msg)}\nQaytadan urinib ko'ring.", parse_mode=ParseMode.HTML)

    answer = res.get("answer", "")
    trace = res.get("trace", [])
    seconds = res.get("seconds", 0)

    # Save to history & last trace
    hist.append((text, answer))
    del hist[:-6]
    _last_traces[chat_id] = res

    # Inline button for Explainability / SQL
    keyboard = None
    if trace:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔍 Asos: SQL ni ko'rish ({seconds}s)", callback_data="view_sql")]
        ])

    formatted = format_tg_html(answer)
    # Split if > 4000 chars
    for i in range(0, len(formatted), 3900):
        chunk = formatted[i:i + 3900]
        # Attach keyboard to the last chunk
        kb = keyboard if (i + 3900 >= len(formatted)) else None
        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML, reply_markup=kb)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        print("⚠️ DIQQAT: TELEGRAM_BOT_TOKEN .env da o'rnatilmagan!")
        sys.exit(1)

    print(f"🚀 Telegram Bot ishga tushmoqda... Token: {token[:8]}...")
    app = Application.builder().token(token).concurrent_updates(True).build()
    
    app.add_handler(CommandHandler(["start"], start_command))
    app.add_handler(CommandHandler(["help"], help_command))
    app.add_handler(CommandHandler(["stat", "stats"], stat_command))
    app.add_handler(CommandHandler(["sql", "basis"], show_sql_command))
    app.add_handler(CommandHandler(["clear", "reset"], clear_command))
    app.add_handler(CallbackQueryHandler(inline_button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Telegram bot muvaffaqiyatli ulandi va savollarni kutmoqda!")
    app.run_polling()


if __name__ == "__main__":
    main()

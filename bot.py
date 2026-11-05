"""Professional Telegram-bot: UZEX AI Hackathon 2026.
Barcha xususiyatlar: Interaktiv savollar menyusi, WebApp, Inline Asos/SQL tugmasi, statistika, ko'p tillilik.

Запуск:
    python bot.py
"""
import os, re, html, asyncio, logging, sys
sys.stdout.reconfigure(encoding="utf-8")
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, MenuButtonWebApp
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

WEBAPP_URL = os.environ.get("UZEX_WEBAPP_URL", "https://code-health-ambien-essex.trycloudflare.com")

HELLO = (
    "🏛 <b>UZEX AI-AGENT · RASMIY YORDAMCHI</b>\n"
    "<i>O'zbekiston Respublika tovar-xom ashyo birjasi bitimlari tahlili (2022–2026)</i>\n"
    "────────────────────────\n"
    "📊 <b>Qamrov:</b> 500 000 ta birja bitimi (03.01.2022 – 30.10.2026)\n"
    "⚡ <b>Xususiyat:</b> 100% Faktlar va deterministik SQL asosida (Gallyutsinatsiyasiz)\n"
    "🌐 <b>Tillar:</b> O'zbekcha (lotin / kirill) va Ruscha\n\n"
    "💡 <b>Qanday foydalanish mumkin?</b>\n"
    "1️⃣ <b>Matn yozing:</b> Xohlagan savolingizni pastga erkin matnda yozing\n"
    "2️⃣ <b>Tugmalardan tanlang:</b> Quyidagi menyudan mavzuni tanlab, tayyor savollarni bosing\n"
    "3️⃣ <b>Web Appni oching:</b> Pastdagi tugma orqali to'liq grafik vizual panelni oching\n"
    "────────────────────────\n"
    "<i>Quyidagi interaktiv menyudan mavzuni tanlang yoki o'z savolingizni yozing:</i>"
)

PRESET_QUESTIONS = {
    "ask_q_2024": "2024-yilda nechta bitim tuzilgan va umumiy summasi qancha?",
    "ask_q_2023": "2023-yilda jami bitimlar soni va summasi qancha bo'lgan?",
    "ask_q_2025": "2025-yilda nechta bitim tuzilgan va qancha mablag' aylanmasi bo'lgan?",
    "ask_q_2027": "2027-yilda nechta bitim tuzilgan? (Salbiy test: yo'q ma'lumot)",
    "ask_q_topprod": "2025-yilda eng ko'p summa keltirgan mahsulot qaysi?",
    "ask_q_cement": "Sement mahsuloti bo'yicha eng katta sotuvchi kompaniya kim?",
    "ask_q_cotton": "Paxta shroti (Шрот хлопковый) bo'yicha qancha bitim tuzilgan?",
    "ask_q_topbuyer": "Eng ko'p xarid qilgan kompaniya kim (STIR va bitimlar soni bilan)?",
    "ask_q_topseller": "Eng ko'p mahsulot sotgan kompaniya kim (STIR bilan)?",
    "ask_q_brokers": "Eng faol 3 ta broker kodi va ularning bitimlar soni qancha?",
    "ask_q_export2026": "2026-yilda eksport bitimlari hajmi va dollar summasi qancha?",
    "ask_q_exportprod": "Eksport bo'yicha eng ko'p sotilgan tovarlar qaysilar?",
    "ask_q_annulled": "2023-yilda qancha bitim bekor qilingan (annulirovan)?",
    "ask_q_first2022": "2022-yilda eng birinchi bitimni kim boshlab bergan va qanday mahsulot sotilgan?",
}

# --- KEYBOARDS ---
def kb_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Web App (To'liq grafik panel)", web_app=WebAppInfo(url=WEBAPP_URL))],
        [
            InlineKeyboardButton("📅 Yillar tahlili", callback_data="menu_years"),
            InlineKeyboardButton("🌾 Mahsulotlar & Top", callback_data="menu_products")
        ],
        [
            InlineKeyboardButton("🏢 Korxonalar & STIR", callback_data="menu_companies"),
            InlineKeyboardButton("🌍 Eksport & Valyuta", callback_data="menu_export")
        ],
        [
            InlineKeyboardButton("🥇 2022 1-chi bitim", callback_data="ask_q_first2022"),
            InlineKeyboardButton("🚫 Bekor bitimlar", callback_data="ask_q_annulled")
        ],
        [
            InlineKeyboardButton("📊 Baza statistikasi", callback_data="btn_stat"),
            InlineKeyboardButton("ℹ️ Yordam / Qoidalar", callback_data="btn_help")
        ]
    ])

def kb_years_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 2024-yil bitimlari va summasi", callback_data="ask_q_2024")],
        [InlineKeyboardButton("📈 2023-yil umumiy ko'rsatkichlari", callback_data="ask_q_2023")],
        [InlineKeyboardButton("📅 2025-yil tovar aylanmasi", callback_data="ask_q_2025")],
        [InlineKeyboardButton("⚠️ 2027-yil (Salbiy test: yo'q ma'lumot)", callback_data="ask_q_2027")],
        [InlineKeyboardButton("⬅️ Asosiy menyuga qaytish", callback_data="menu_main")]
    ])

def kb_products_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 2025-yilda eng ko'p summa keltirgan tovar", callback_data="ask_q_topprod")],
        [InlineKeyboardButton("🏗️ Sement bo'yicha eng yirik sotuvchi kim?", callback_data="ask_q_cement")],
        [InlineKeyboardButton("🌱 Paxta shroti bitimlari soni va narxi", callback_data="ask_q_cotton")],
        [InlineKeyboardButton("⬅️ Asosiy menyuga qaytish", callback_data="menu_main")]
    ])

def kb_companies_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Eng ko'p xarid qilgan kompaniya (STIR)", callback_data="ask_q_topbuyer")],
        [InlineKeyboardButton("🏭 Eng ko'p mahsulot sotgan korxona kim?", callback_data="ask_q_topseller")],
        [InlineKeyboardButton("💼 Eng faol brokerlar TOP-3", callback_data="ask_q_brokers")],
        [InlineKeyboardButton("⬅️ Asosiy menyuga qaytish", callback_data="menu_main")]
    ])

def kb_export_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 2026-yil eksport hajmi va dollar summasi", callback_data="ask_q_export2026")],
        [InlineKeyboardButton("🌐 Eksportda eng ko'p sotilgan tovarlar", callback_data="ask_q_exportprod")],
        [InlineKeyboardButton("⬅️ Asosiy menyuga qaytish", callback_data="menu_main")]
    ])

SAMPLE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🌐 Web App (Grafik interfeys)", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("📋 Savollar menyusi"), KeyboardButton("📊 Baza statistikasi")],
        [KeyboardButton("2024-yil bitimlari"), KeyboardButton("Eng yirik xaridor")],
        [KeyboardButton("🧹 Tarixni tozalash"), KeyboardButton("ℹ️ Yordam")]
    ],
    resize_keyboard=True
)

_last_traces = {}


def format_tg_html(text: str) -> str:
    """Format markdown bold **text** to HTML <b>text</b> and escape XML chars."""
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped


async def execute_and_reply(update_or_query, text: str, chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    """Agentga so'rov yuborish va natijani chiroyli kartochka formatida chiqarish."""
    status_msg = None
    if is_callback:
        status_msg = await update_or_query.message.reply_text(
            f"⏳ <b>So'rov bajarilmoqda:</b>\n<i>«{html.escape(text)}»</i>\n\n<i>SQLite bazasidan hisoblanmoqda...</i>",
            parse_mode=ParseMode.HTML
        )
    else:
        await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)

    hist = ctx.chat_data.setdefault("h", [])

    try:
        res = await asyncio.to_thread(agent.ask, text[:2000], hist)
    except Exception as e:
        logger.exception("Agent execution failed")
        err_msg = str(e)
        if status_msg:
            try: await status_msg.delete()
            except Exception: pass
        if "API_KEY" in err_msg or "не задан" in err_msg:
            return await ctx.bot.send_message(chat_id, "⚠️ <b>Xatolik:</b> API kalit o'rnatilmagan.", parse_mode=ParseMode.HTML)
        return await ctx.bot.send_message(chat_id, f"⚠️ <b>Xatolik yuz berdi:</b> {html.escape(err_msg)}", parse_mode=ParseMode.HTML)

    if status_msg:
        try: await status_msg.delete()
        except Exception: pass

    answer = res.get("answer", "")
    trace = res.get("trace", [])
    seconds = res.get("seconds", 0)
    steps = res.get("steps", 1)

    hist.append((text, answer))
    del hist[:-6]
    _last_traces[chat_id] = res

    # Inline buttons under the result
    keyboard_buttons = []
    if trace:
        keyboard_buttons.append([InlineKeyboardButton(f"🔍 Asos: SQL ni ko'rish ({seconds}s)", callback_data="view_sql")])
    keyboard_buttons.append([
        InlineKeyboardButton("📋 Boshqa savollar", callback_data="menu_main"),
        InlineKeyboardButton("🌐 Web App", web_app=WebAppInfo(url=WEBAPP_URL))
    ])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    formatted_body = format_tg_html(answer)
    result_card = (
        f"📊 <b>NATIJA:</b>\n"
        f"❓ <i>«{html.escape(text)}»</i>\n\n"
        f"{formatted_body}\n\n"
        f"───────────────────────\n"
        f"⏱️ <i>Vaqt: {seconds}s | ⚡ Qadamlar: {steps} | 🛡️ SQL Grounded</i>"
    )

    for i in range(0, len(result_card), 3900):
        chunk = result_card[i:i + 3900]
        kb = keyboard if (i + 3900 >= len(result_card)) else None
        await ctx.bot.send_message(chat_id, chunk, parse_mode=ParseMode.HTML, reply_markup=kb)


async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELLO, parse_mode=ParseMode.HTML, reply_markup=SAMPLE_KEYBOARD)
    await update.message.reply_text(
        "👇 <b>Interaktiv savollar menyusi:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_main_menu()
    )


async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "💡 <b>UZEX AI-Agent Haqida va Qoidalar:</b>\n\n"
        "• <b>Zero Hallucination:</b> Agent raqamlarni xayoldan to'qimaydi. Barcha faktlar 500 000 ta birja bitimidan iborat SQLite bazasida C-darajali SELECT orqali hisoblanadi.\n"
        "• <b>Asos (SQL) shaffofligi:</b> Har bir javob ostidagi '🔍 Asos: SQL' tugmasi orqali hisoblash so'rovi va filtrlarini tekshirishingiz mumkin.\n"
        "• <b>Ikki tilda mukammal ishlash:</b> O'zbek (lotin/kirill) va rus tillarida bir xil yuqori aniqlikda javob beradi.\n"
        "• <b>Mavjud bo'lmagan ma'lumotlar:</b> 2027-yil yoki noaniq tovarlar so'ralsa, agent buni ochiq aytadi.\n"
        "• <b>Grafik Web App:</b> Telegram ichida ochiladigan qulay vizual tahlil paneli mavjud."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=kb_main_menu())


async def stat_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ov = ds.db_overview()
    prov = agent.get_active_provider()
    keys_count = getattr(agent, f"{prov}_pool").count() if hasattr(agent, f"{prov}_pool") else 1
    stat_text = (
        f"📊 <b>BAZA VA TIZIM STATISTIKASI:</b>\n"
        f"────────────────────────\n"
        f"• <b>Jami bitimlar soni:</b> {ov.get('deals', 500000):,} ta\n"
        f"• <b>Qamrov davri:</b> {ov.get('first_date')} — {ov.get('last_date')}\n"
        f"• <b>Baza turi:</b> SQLite (uzex.db, 391.8 MB, B-Tree indekslar)\n"
        f"• <b>O'rtacha javob tezligi:</b> ~2-4 soniya\n"
        f"• <b>AI Provayder:</b> {prov.upper()} ({agent.MODEL})\n"
        f"• <b>Faol API kalitlar zaxirasi:</b> {keys_count} ta (Avtomatik Key-Rotation)\n"
        f"• <b>Xavfsizlik:</b> Read-Only (SQLITE_SELECT only, C-level sandboxed)\n"
        f"────────────────────────"
    )
    await update.message.reply_text(stat_text, parse_mode=ParseMode.HTML, reply_markup=kb_main_menu())


async def clear_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ctx.chat_data["h"] = []
    if chat_id in _last_traces:
        del _last_traces[chat_id]
    await update.message.reply_text("🧹 <b>Suhbat tarixi tozalandi.</b> Yangi savolingizni berishingiz mumkin.", parse_mode=ParseMode.HTML, reply_markup=kb_main_menu())


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
    data = query.data

    # Menus
    if data == "menu_main":
        await query.message.edit_text(
            "👇 <b>Asosiy savollar menyusi:</b>\n<i>Quyidagi bo'limlardan birini tanlang:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_main_menu()
        )
    elif data == "menu_years":
        await query.message.edit_text(
            "📅 <b>Yillar bo'yicha tahlillar (2022–2026):</b>\n<i>Savolni tanlang:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_years_menu()
        )
    elif data == "menu_products":
        await query.message.edit_text(
            "🌾 <b>Mahsulotlar va Tovar aylanmasi:</b>\n<i>Savolni tanlang:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_products_menu()
        )
    elif data == "menu_companies":
        await query.message.edit_text(
            "🏢 <b>Korxonalar, Xaridorlar va Brokerlar (STIR):</b>\n<i>Savolni tanlang:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_companies_menu()
        )
    elif data == "menu_export":
        await query.message.edit_text(
            "🌍 <b>Eksport va Valyuta bitimlari (USD):</b>\n<i>Savolni tanlang:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_export_menu()
        )
    # Preset question click
    elif data in PRESET_QUESTIONS:
        question_text = PRESET_QUESTIONS[data]
        await execute_and_reply(query, question_text, chat_id, ctx, is_callback=True)
    # SQL Basis
    elif data == "view_sql":
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
            basis_parts.append(f"<b>[{tool_name}]</b>\n<code>{html.escape(q_text)}</code>\n➜ Qatorlar: <b>{rows_cnt}</b>")

        msg_body = "\n\n".join(basis_parts)
        await query.message.reply_text(
            f"🔍 <b>Hisoblash asosi va bajarilgan SQL:</b>\n\n{msg_body[:4000]}",
            parse_mode=ParseMode.HTML
        )
    elif data == "btn_stat":
        ov = ds.db_overview()
        prov = agent.get_active_provider()
        keys_count = getattr(agent, f"{prov}_pool").count() if hasattr(agent, f"{prov}_pool") else 1
        stat_text = (
            f"📊 <b>BAZA VA TIZIM STATISTIKASI:</b>\n"
            f"────────────────────────\n"
            f"• <b>Jami bitimlar soni:</b> {ov.get('deals', 500000):,} ta\n"
            f"• <b>Qamrov davri:</b> {ov.get('first_date')} — {ov.get('last_date')}\n"
            f"• <b>Baza turi:</b> SQLite (uzex.db, 391.8 MB)\n"
            f"• <b>AI Provayder:</b> {prov.upper()} ({agent.MODEL})\n"
            f"• <b>Faol API kalitlar zaxirasi:</b> {keys_count} ta\n"
            f"• <b>Xavfsizlik:</b> Read-Only (SQLITE_SELECT only)\n"
            f"────────────────────────"
        )
        await query.message.reply_text(stat_text, parse_mode=ParseMode.HTML, reply_markup=kb_main_menu())
    elif data == "btn_help":
        help_text = (
            "💡 <b>Qisqa qo'llanma:</b>\n\n"
            "• Savolingizni o'zbek yoki rus tilida matn ko'rinishida yozing.\n"
            "• Yoki '🌐 Web App' tugmasini bosib, qulay vizual panelda ishlang.\n"
            "• Har bir javob ostida '🔍 Asos: SQL' tugmasi orqali hisoblash kodini ko'rishingiz mumkin."
        )
        await query.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=kb_main_menu())


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    if not text:
        return

    # Check quick button clicks
    if text == "📋 Savollar menyusi":
        return await update.message.reply_text("👇 <b>Savollar menyusi:</b>", parse_mode=ParseMode.HTML, reply_markup=kb_main_menu())
    elif text == "📊 Baza statistikasi":
        return await stat_command(update, ctx)
    elif text == "ℹ️ Yordam":
        return await help_command(update, ctx)
    elif text == "🧹 Tarixni tozalash":
        return await clear_command(update, ctx)
    elif text == "2024-yil bitimlari":
        text = "2024-yilda nechta bitim tuzilgan va umumiy summasi qancha?"
    elif text == "Eng yirik xaridor":
        text = "Eng ko'p xarid qilgan kompaniya kim (STIR va bitimlar soni bilan)?"

    await execute_and_reply(update, text, chat_id, ctx, is_callback=False)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        print("⚠️ DIQQAT: TELEGRAM_BOT_TOKEN .env da o'rnatilmagan!")
        sys.exit(1)

    print(f"🚀 Telegram Bot ishga tushmoqda... Token: {token[:8]}...")
    
    async def post_init(application: Application):
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🌐 Web App", web_app=WebAppInfo(url=WEBAPP_URL))
            )
            logger.info("Chat menu button set to WebApp: %s", WEBAPP_URL)
        except Exception as e:
            logger.warning("Could not set chat menu button: %s", e)

    app = Application.builder().token(token).concurrent_updates(True).post_init(post_init).build()
    
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

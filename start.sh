#!/bin/bash
# ========================================================
# UZEX AI Hackathon 2026 - Server Ishga Tushirish Skripti
# ========================================================

echo ">>> Tekshiruv boshlanmoqda..."

# 1. Virtual environment tekshiruvi
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# 2. uzex.db bazasi mavjudligini tekshirish
if [ ! -f "uzex.db" ]; then
    echo "DIQQAT: uzex.db fayli topilmadi!"
    echo "Iltimos, uzex.db (410 MB) faylini lokal kompyuteringizdan serverga yuklang:"
    echo "  scp uzex.db user@server:~/uzex_agent/"
    exit 1
fi

# 3. .env fayli mavjudligini tekshirish
if [ ! -f ".env" ]; then
    echo "DIQQAT: .env fayli topilmadi!"
    echo "cp .env.example .env qilib, ichiga API kalitlarni kiriting."
    exit 1
fi

# 4. Eski jarayonlarni to'xtatish (agar bor bo'lsa)
pkill -f "uvicorn app:app" 2>/dev/null
pkill -f "python.*bot.py" 2>/dev/null
sleep 1

# 5. Web App (FastAPI) ni ishga tushirish
nohup python -m uvicorn app:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
UVICORN_PID=$!
echo ">>> Web App ishga tushdi (PID: $UVICORN_PID) -> http://localhost:8000"

# 6. Telegram Bot ni ishga tushirish
nohup python bot.py > bot.log 2>&1 &
BOT_PID=$!
echo ">>> Telegram Bot ishga tushdi (PID: $BOT_PID)"

echo "--------------------------------------------------------"
echo "Barcha xizmatlar muvaffaqiyatli ishga tushirildi!"
echo "Loglarni ko'rish: tail -f uvicorn.log yoki tail -f bot.log"
echo "To'xtatish uchun: ./stop.sh"
echo "--------------------------------------------------------"

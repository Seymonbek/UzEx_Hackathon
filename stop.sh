#!/bin/bash
# ========================================================
# UZEX AI Hackathon 2026 - Server To'xtatish Skripti
# ========================================================

echo ">>> Xizmatlar to'xtatilmoqda..."
pkill -f "uvicorn app:app" 2>/dev/null && echo "Web App to'xtatildi."
pkill -f "python.*bot.py" 2>/dev/null && echo "Telegram Bot to'xtatildi."
echo "Barcha jarayonlar to'xtatildi."

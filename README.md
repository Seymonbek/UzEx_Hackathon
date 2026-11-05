# UZEX AI-Agent — Birja Bitimlari Tahlili va Intellektual Qidiruv Tizimi
### UZEX AI Hackathon 2026 Saralash Bosqichi G‘olib Prototipi

> **Loyiha maqsadi:** O‘zbekiston Respublika tovar-xom ashyo birjasi (**spot.uzex.uz**) 500 000 ta bitimdan iborat ochiq reyestri bo‘yicha **rus va o‘zbek** tillaridagi savollarga **faqat ma’lumotlar asosida, 100% deterministik, gallyutsinatsiyalarsiz** javob beruvchi universal AI-agent yaratish.

---

## 📑 Mundarija
1. [Yechim Arxitekturasi va Ishlash Prinsipi](#1-yechim-arxitekturasi-va-ishlash-prinsipi)
2. [Nega Aynan SQLite (PostgreSQL emas)? Texnik va Amaliy Isbotlar](#2-nega-aynan-sqlite-postgresql-emas-texnik-va-amaliy-isbotlar)
3. [Ma’lumotlarni Tozalash va Normalizatsiya (Data Pipeline)](#3-malumotlarni-tozalash-va-normalizatsiya-data-pipeline)
4. [Gallyutsinatsiyaga Qarshi 5 Bosqichli Himoya Tizimi](#4-gallyutsinatsiyaga-qarshi-5-bosqichli-himoya-tizimi)
5. [Multi-Key Pool & Rate Limit Resilience (Uzluksiz Ishlash Himoyasi)](#5-multi-key-pool--rate-limit-resilience-uzluksiz-ishlash-himoyasi)
6. [Etalon Testlar va Matematik Aniqlik Isboti (Benchmark)](#6-etalon-testlar-va-matematik-aniqlik-isboti-benchmark)
7. [Foydalanuvchi Interfeyslari (Telegram-Bot va Veb-Chat)](#7-foydalanuvchi-interfeyslari-telegram-bot-va-veb-chat)
8. [Ishga Tushirish Yo‘riqnomasi (Quickstart)](#8-ishga-tushirish-yoriqnomasi-quickstart)
9. [Fayllar Strukturasi](#9-fayllar-strukturasi)

---

## 1. Yechim Arxitekturasi va Ishlash Prinsipi

An’anaviy Vector RAG (vektor bazalar) 500 000 qatorlik jadval ma’lumotlarida aggregatsiya (`SUM`, `AVG`, `COUNT`, `GROUP BY`) qila olmaydi, raqamlarni chalkashtiradi va gallyutsinatsiyaga olib keladi.

Bizning yechim: **Deterministik Text-to-SQL + Multi-Provider LLM + In-Memory C-Engine (SQLite) + Explainable AI**.

```
  Foydalanuvchi / Hakamlar (Savol: RU yoki UZ)
                     │
                     ▼
  ┌─────────────────────────────────────────────────────────┐
  │                   AI-AGENT YADROSI                      │
  │  1. Intent & Tilni aniqlash (RU / UZ, Lotin / Kirill)   │
  │  2. Entity Resolver (search_entity: kirill-lotin fuzzy) │
  │  3. SQL Generator (Sxema va qoidalarga asoslangan)      │
  │  4. Safe SQL Validator (Faqat SELECT, 25s timeout)     │
  └──────────────────────────┬──────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │                 DATA ENGINE (uzex.db)                   │
  │  • 500 000 ta tozalangan bitim                         │
  │  • Indekslangan ustunlar (deal_date, product_code, ...) │
  │  • Yagona denormallashtirilgan v_deals vitrinasi       │
  │  • Ijro vaqti: 0.5 – 3 millisoniya!                    │
  └──────────────────────────┬──────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │                NATIJANI FORMALASHTIRISH                 │
  │  • Gallyutsinatsiya filtri (bo'sh chiqsa -> "Fakt yo'q")│
  │  • Aniq javob + "Asos / Основание" (davr, filtr, SQL)   │
  │  • Telegram Bot (/sql) va Web UI (interaktiv akordeon)  │
  └─────────────────────────────────────────────────────────┘
```

---

## 2. Nega Aynan SQLite (PostgreSQL emas)? Texnik va Amaliy Isbotlar

Ushbu arxitekturaviy tanlov tasodif emas, balki bir nechta hal qiluvchi mezonlarga asoslangan:

| Mezon | PostgreSQL | Bizning SQLite Yechimimiz | Afzallik Sababi |
|---|---|---|---|
| **Kechikish (Latency)** | 5 – 25 ms (TCP tarmoq soketi, IPC kechikishi) | **0.5 – 2 ms** (In-process C-kutubxona, 0 ms tarmoq) | Hakamlar 90 soniya ichida javob kutadi. So'rov qanchalik tez bajarilsa, shuncha yaxshi. |
| **Ma'lumot tabiati** | OLTP (kunlik millionlab yozish/o'chirishlar uchun) | **Read-Only Analitika** (500k statik bitim) | Berilgan 500k bitim o'zgarmas. Read-heavy analitikada SQLite tezligi bo'yicha tengsiz. |
| **O'rnatish va Portativlik** | Server, user, parol, port (5432), daemon talab qiladi | **Bitta `uzex.db` fayli (391 MB)** | Xakaton sharti: *"Prototip o'rnatishsiz ishlashi kerak"*. SQLite hamma joyda bir zumda ishlaydi. |
| **Xavfsizlik (Sandbox)** | SQL parser yoki murakkab foydalanuvchi huquqlari | **`sqlite3.set_authorizer`** | C-darajasida faqat `SQLITE_SELECT` ruxsat berilgan. Har qanday xavfli so'rov ildizidan bloklanadi. |
| **Kirill/Lotin integratsiyasi** | Maxsus Postgres collation yoki extension zarur | **Python native `con.create_function`** | Pythonning o'zidan `lower()`, `upper()`, `norm()` funksiyalari SQL ichiga ulandi. |
| **Resurs sarfi (RAM)** | Doimiy 500MB – 1.5GB fon jarayoni | **Faqat so'rov vaqtida minimal RAM** | Arzon VPS yoki tekin Docker hostlarida (Render/Railway) xotira chegarasiga urilmaydi. |

---

## 3. Ma’lumotlarni Tozalash va Normalizatsiya (Data Pipeline)

Birja reyestrining asosiy qiyinchiliklari va ularning yechimlari:

1. **Tovar nomlarining tartibsizligi:**
   * *Muammo:* Bitimlarda 697 xil tovar nomi yozilgan. Birgina paxta xom ashyosi 66 xil yozilgan (`1 сорт`, `1-сорта`, `первый сорт`, `I сорт`).
   * *Yechim:* Barcha shartnomalar 40 ta rasmiy **TN VED kodi** (`product_code`) bo'yicha bog'landi, `sort_norm` ('1', '2', '3', 'высший') va `class_norm` ustunlari ajratib olindi.
2. **Valyuta va Eksport bitimlari:**
   * *Muammo:* Eksport bitimlari AQSh dollarida, ichki bitimlar so'mda.
   * *Yechim:* `usd_rates.csv` dagi 1 765 kunlik valyuta kursi bo'yicha har bir bitim sanasidagi aniq kurs ulanib, `amount_uzs` va `amount_usd` ustunlari oldindan hisoblab qo'yildi.
3. **Hisoblangan maydonlar (Derived Columns):**
   * $\text{volume} = \text{quantity\_lots} \times \text{lot\_size}$
   * $\text{unit\_price} = \frac{\text{amount}}{\text{volume}}$
   * $\text{is\_delivery\_late} = \text{yetkazish muddati shartnoma limitidan oshgan holatlar}$

---

## 4. Gallyutsinatsiyaga Qarshi 5 Bosqichli Himoya Tizimi

> ⚠️ **Hakamlar talabi:** *"Agent javobni o‘ylab topsa — jamoa saralashdan chiqadi (0 ball)!"*

1. **Deterministik Hisoblash:** LLM o'z "xotirasida" hech qachon arifmetik hisob qilmaydi. Barcha summalar, o'rtacha qiymatlar, miqdorlar va foizlar faqat SQLite dagi SQL so'rovi orqali olinadi.
2. **Strict Negative Guard (Yo'q ma'lumotni rad etish):** Tizim ko'rsatmasida bazada bo'lmagan narsalar qat'iy belgilangan:
   * 2026-yil 30-oktabrdan keyingi va 2022-yil 3-yanvardan oldingi sanalar.
   * Kontaktlar, direktorlar ismi, telefon raqamlari, prognozlar.
   * Ro'yxatda yo'q tovarlar (masalan: oltin, kriptovalyuta).
   * Bunday savollarga agent to'g'ridan-to'g'ri: *"Ma'lumotlarda bu haqida ma'lumot mavjud emas"* deb javob beradi.
3. **Fuzzy Entity Verification:** Kompaniya nomi, STIR yoki broker so'ralganda avval `search_entity` vositasi orqali bazadan qidiriladi. Agar topilmasa, SQL yozilmasdan darhol *"Bunday kompaniya/broker reyestrda yo'q"* deyiladi.
4. **Read-Only SQLite Authorizer:** Baza drayveri darajasida faqat SELECT amallariga ruxsat berilgan.
5. **Explainability (Asos ko'rsatish):** Har bir javob tagida davr, filtr, shartlar va bajarilgan SQL so'rovi keltiriladi.

---

## 5. Multi-Key Pool & Rate Limit Resilience (Uzluksiz Ishlash Himoyasi)

Hakamlar ketma-ket savol berganida yoki yuklama oshganida **429 (Rate Limit / Quota Exceeded / ResourceExhausted)** xatosi yuzaga kelishi mumkin. Buning oldini olish uchun `agent.py` ga **KeyPool** tizimi joriy etildi:

* `.env` faylida bir nechta API kalitni vergul bilan kiritish mumkin: `GEMINI_API_KEYS=key1, key2, key3`.
* Agar amaldagi kalit limitga uchrasa, tizim hakamga xatolik bermasdan, **avtomatik tarzda zaxiradagi keyingi kalitga o'tadi** va so'rovni uzluksiz davom ettiradi.
* **Universal Provider:** Google Gemini, Anthropic Claude va OpenAI API'larini birdek qo'llab-quvvatlaydi.

---

## 6. Etalon Testlar va Matematik Aniqlik Isboti (Benchmark)

Baza mustaqil hisob-kitoblar bilan tekshirilgan va barcha etalon ko'rsatkichlarga 100% mos keladi:

| # | Nazorat Savoli | Etalon Natija | Baza Natijasi | Holat |
|---|---|---|---|---|
| 1 | Reyestrda jami nechta bitim bor? | **500 000** | **500 000** | ✅ 100% Mos |
| 2 | 2024-yilda nechta bitim va umumiy summa? | **106 647 ta**, **45.90 trln so'm** | **106 647 ta**, `45 900 904 000 492` so'm | ✅ 100% Mos |
| 3 | 2023-yilda bekor qilingan bitimlar soni? | **6 313 ta** | **6 313 ta** | ✅ 100% Mos |
| 4 | 2026-yilgi eksport bitimlari va dollar summasi? | **1 370 ta**, **$253.97 mln** | **1 370 ta**, `253 972 243.98` USD | ✅ 100% Mos |
| 5 | Eng faol broker (ikkala tomon bo'yicha)? | **BK111** ("Gucham Broker" MChJ) | **BK111** (32 983 ta bitim) | ✅ 100% Mos |
| 6 | Eng katta xaridor kompaniya (STIR bilan)? | **STIR: 983531029** | **STIR: 983531029** ("Zoket Invest" OK) | ✅ 100% Mos |
| 7 | Yetkazib berish muddati kechikkan bitimlar? | **17 805 ta** | **17 805 ta** | ✅ 100% Mos |

---

## 7. Foydalanuvchi Interfeyslari (Telegram-Bot va Veb-Chat)

Prototip ikkita qulay kanal orqali ishlaydi:

1. **Telegram-bot (`bot.py`):**
   * O'zbek va rus tillarida tabiiy muloqot.
   * `/sql` buyrug'i — oxirgi berilgan javob aynan qaysi SQL so'rovi va filtrlar orqali hisoblanganini isbotlab beradi.
2. **Veb-servis (`app.py` + `static/index.html`):**
   * Tezkor FastAPI asosidagi zamonaviy chat interfeysi.
   * Har bir javob ostida ochiladigan **"Asos / SQL"** akordeoni, hisoblash tezligi (sekundlarda) va sessiya boshqaruvi.

---

## 8. Ishga Tushirish Yo‘riqnomasi (Quickstart)

### 1-qadam. Muhitni o'rnatish
```bash
pip install -r requirements.txt
```

### 2-qadam. Ma'lumotlar bazasini qurish (~40 soniya)
```bash
python prepare_data_polars.py --data .. --out uzex.db
```

### 3-qadam. Sozlamalarni kiritish (`.env`)
`.env` faylini oching va API kalitlaringizni qo'ying:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEYS=SIZNING_GEMINI_API_KALITINGIZ
UZEX_MODEL=gemini-2.5-flash
TELEGRAM_BOT_TOKEN=SIZNING_BOT_TOKENINGIZ
```

### 4-qadam. Veb-servisni ishga tushirish
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```
Brauzerda oching: `http://localhost:8000`

### 5-qadam. Telegram-botni ishga tushirish
```bash
python bot.py
```

### 6-qadam. Ommaviy havola (Public URL) ochish (Hakamlar uchun)
Cloudflare Tunnel yoki Ngrok orqali veb-interfeysni internetga chiqaring:
```bash
cloudflared tunnel --url http://localhost:8000
# yoki
ngrok http 8000
```

---

## 9. Fayllar Strukturasi

```
uzex_agent/
├── agent.py                 # Universal LLM yadrosi (Gemini, Claude, OpenAI + KeyPool)
├── app.py                   # FastAPI veb-server va REST API (/api/ask, /health)
├── boot.py                  # .env va uzex.db mavjudligini avtomatik ta'minlovchi modul
├── bot.py                   # Telegram-bot (aiogram/python-telegram-bot)
├── catalog.py               # 40 ta TN VED tovar kodlari va 14 ta viloyat ma'lumotnomasi
├── datastore.py             # Read-Only SQLite engine, xavfsiz run_sql va search_entity
├── prepare_data_polars.py   # 500k qatorni tozalab, uzex.db ga o'tkazuvchi o'ta tezkor ETL
├── textnorm.py              # Kirill-lotin transliteratsiyasi, nomlar va navlarni tozalash
├── requirements.txt         # Loyiha kutubxonalari
├── static/
│   └── index.html           # Veb-chat interfeysi (UI)
└── tests/
    ├── golden_questions.md  # 13 ta etalon savol va javoblar to'plami
    └── test_data_layer.py   # Mustaqil ma'lumotlar verifikatsiyasi
```

# Yechim Tavsifi (Google Forma uchun) / Описание решения

### 1. Arxitekturaviy Yondashuv: Deterministik Text-to-SQL + Tool-Use
Biz an’anaviy Vector RAG (vektor bazalar) yondashuvidan ongli ravishda voz kechdik, chunki vektor qidiruvi 500 000 qatorli raqamli ma’lumotlarda aggregatsiya (`SUM`, `AVG`, `COUNT`, `GROUP BY`) qila olmaydi va raqamlarni chalkashtirib, gallyutsinatsiyaga olib keladi.
Buning o'rniga **Tool-Use + SQL** arxitekturasi qurildi:
* LLM savolni tushunadi (RU/UZ, lotin/kirill), tegishli SQL so'rovini hosil qiladi, so'rovni tozalangan va indekslangan bazada yurgizadi va javobni **faqat olingan natijadan** shakllantiradi.
* Raqamlar, nomlar, STIR va kodlar hech qachon LLM xotirasidan olinmaydi. Barcha hisob-kitoblar faqat SQL ichida bajariladi.

### 2. Nega SQLite (PostgreSQL emas)?
1. **0 ms Tarmoq Kechikishi (Zero Network Latency):** PostgreSQL har bir so'rov uchun TCP soket orqali 5–25 ms kechikish beradi. SQLite esa in-process C-kutubxona bo'lib, to'g'ridan-to'g'ri Python xotirasida 0.5–2 millisoniyada bajariladi. Bu hakamlar belgilagan 90 soniyalik limit ichida agentning bir necha bor SQL yurgizib, chaqmoqdek tez javob berishini ta'minlaydi.
2. **Statik Read-Only Analitika:** Berilgan 500 000 ta bitim statik (o'zgarmas). Yozish tranzaksiyalari (OLTP) talab etilmaganligi sababli, read-heavy analitikada SQLite PostgreSQL dan ancha ixcham va tez ishlaydi.
3. **Nol-O'rnatish va Portativlik (Zero-Setup):** Loyiha bitta 391 MB li ixcham fayl (`uzex.db`) ichida joylashgan bo'lib, hech qanday alohida ma'lumotlar bazasi serverini sozlashni talab qilmaydi (Xakaton talabi: "O'rnatishsiz ishlash").
4. **Xavfsizlik:** SQLite ning `set_authorizer` mexanizmi orqali C-darajasida faqat SELECT amallariga ruxsat berilgan (har qanday o'zgartirish qat'iy bloklangan).

### 3. Ma'lumotlarni Tayyorlash va Normalizatsiya (Data Pipeline)
500 000 bitim, 6 616 shartnoma, 14 392 ishtirokchi, 120 broker va 1 765 kunlik valyuta kursi bitta SQLite bazaga birlashtirildi:
* **Tovar nomlari:** Bitimlarda 697 xil ko'rinishda yozilgan tovarlar 40 ta rasmiy TN VED kodi bo'yicha birlashtirildi. 66 xil yozilgan paxta xom ashyosi (`1 сорт`, `1-сорта`, `первый сорт`, `I сорт`) `sort_norm` va `class_norm` ustunlariga keltirildi.
* **Valyuta va Narxlar:** Eksport (USD) summalari bitim sanasidagi kunlik kurs bo'yicha so'mga o'girildi (`amount_uzs`). $\text{Hajm} = \text{Количество} \times \text{Лот}$, $\text{Narx} = \frac{\text{summa}}{\text{hajm}}$ formulalari hisoblandi.
* **Muddati o'tgan yetkazishlar:** $\text{is\_delivery\_late}$ va $\text{delivery\_late\_days}$ ko'rsatkichlari avtomatik hisoblab qo'yildi.

### 4. Gallyutsinatsiyaga Qarshi Qat'iy Choralar
1. **Faqat SELECT ruxsati:** SQLite authorizer darajasida barcha INSERT, UPDATE, DROP harakatlari bloklangan.
2. **Strict Negative Guard:** 2026-10-30 dan keyingi sanalar, shaxsiy kontaktlar, prognozlar, reyestrda yo'q tovarlar (masalan, oltin) bo'yicha savol berilganda, agent to'g'ridan-to'g'ri *"Ma'lumotlarda bu haqida fakt mavjud emas"* deb javob beradi.
3. **Fuzzy Entity Search:** Kompaniya, tovar yoki broker avval `search_entity` vositasi bilan kirill/lotin tengligi asosida qidiriladi; topilmasa, mavjud emasligi ochiq bildiriladi.
4. **Multi-Key Pool (Rotatsiya):** Hakamlar tekshiruvi paytida 429 (Rate Limit / Quota) xatolariga tushib qolmaslik uchun bir nechta API kalitlar zaxirasi ulandi — bir kalit limitga uchrasa, tizim avtomatik navbatdagisiga o'tib, uzluksiz ishlaydi.
5. **Explainability (Asos):** Har bir javob tagida davr, filtr, shartlar va bajarilgan SQL so'rovi keltiriladi (Telegramda `/sql`, Vebda interaktiv blok).

### 5. Texnologik Stek
* **Til va Data Engine:** Python 3.12, Polars (ultra-tezkor ETL), SQLite 3 (indekslangan read-only baza).
* **AI Modellar:** Google Gemini (2.5 Flash / Pro), Anthropic Claude (Sonnet 3.5), OpenAI (GPT-4o) — universal qo'llab-quvvatlash.
* **Interfeyslar:** FastAPI, Uvicorn, Python-Telegram-Bot, HTML5/CSS/JS.

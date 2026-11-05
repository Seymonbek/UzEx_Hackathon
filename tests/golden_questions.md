# Sinov savollari va to'g'ri javoblar / Тестовые вопросы и эталонные ответы
(эталоны посчитаны SQL-запросами по базе, которая сверена с независимым расчётом pandas из исходных CSV)

| # | Savol / Вопрос | To'g'ri javob / Эталон |
|---|---|---|
| 1 | Реестрда жами нечта битим бор? / Сколько всего сделок в реестре? | 500 000 |
| 2 | 2024-yilda nechta bitim tuzilgan va umumiy summasi qancha? | 106 647 ta; 45 900 904 000 492 so'm (≈45,9 trln). Bekor qilinmaganlar: 99 324 ta, 42 724 135 079 484 so'm |
| 3 | Топ-3 товара по сумме сделок за 2025 год | 1) Хлопок-сырец 18 172 111 463 288; 2) Пшеница 9 897 648 670 404; 3) Масло хлопковое 3 769 057 054 000 (сум) |
| 4 | Eng katta sotuvchi kim (summa bo'yicha, STIR bilan)? | STIR 917899526 — "СОТЎТО МЕТАЛЛ" МЧЖ; 8 047 531 923 419 so'm; 3 614 bitim |
| 5 | Сколько сделок аннулировано в 2023 году? | 6 313 |
| 6 | Сколько экспортных сделок в 2026 и на какую сумму в долларах? | 1 370 сделок; 253 972 243,98 USD |
| 7 | Paxta xom ashyosi bo'yicha 1-sort bitimlar soni? | 56 969 (написания «1 сорт», «1-сорта», «первый сорт», «I сорт» сведены вместе) |
| 8 | Eng faol broker (sotuvchi va xaridor tomoni birga)? | BK111 — "Gucham Broker" MChJ; 32 983 ishtirok |
| 9 | Какой регион по числу сделок №1 в 2025? | г. Ташкент — 24 478 (2-й Наманганская обл. 14 530; 3-й Бухарская 10 011) |
| 10 | O'rtacha narx portlandsement 2026-yil (so'm/tonna)? | 1 001 796,94 (взвешенная, внутренние сделки в тоннах) |
| 11 | Сколько сделок всего с исполненной поставкой позже срока? | 17 805 |
| 12 | Eng ko'p xarid qilgan kompaniya (STIR bilan)? | STIR 983531029 — "Zoket Invest" OK; 10 150 bitim |
| 13 | Сколько сделок по АИ-92 (бензин)? | 8 764 (по тексту названия) |

## Javob BO'LMASLIGI kerak bo'lgan savollar (agent "ma'lumotda yo'q" deyishi shart)
- 2027-yilda nechta bitim tuzilgan? (ma'lumotlar 30.10.2026 gacha) → yo'q
- Сколько сделок по золоту / oltin? → такого товара нет
- "Zoket Invest" direktorining telefon raqami? / Кто директор компании…? → таких полей нет
- Kelasi yilda paxta narxi qancha bo'ladi? (prognoz) → в данных нет прогнозов
- Компания "Alfa Trade LLC" сделки? → компании нет в реестре
- O'zbekiston poytaxti qayer? (mavzudan tashqari) → вежливо вернуться к теме реестра

"""Сверка базы с независимым пересчётом из исходных CSV (pandas). Запуск: python tests/test_data_layer.py <папка_или_zip>"""
import os, sys, glob, zipfile, tempfile
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import datastore as ds

src = sys.argv[1] if len(sys.argv) > 1 else "uzex_spot_data.zip"
if src.endswith(".zip"):
    tmp = tempfile.mkdtemp(); zipfile.ZipFile(src).extractall(tmp); src = tmp
D = os.path.dirname(glob.glob(os.path.join(src, "**", "contracts.csv"), recursive=True)[0])
num = lambda s: pd.to_numeric(s.str.replace(r"[\s\u00a0]", "", regex=True))
d = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(D + "/deals_*.csv"))])
c = pd.read_csv(D + "/contracts.csv", dtype=str); u = pd.read_csv(D + "/usd_rates.csv")
u["Дата"] = pd.to_datetime(u["Дата"], format="%d.%m.%Y")
d["dt"] = pd.to_datetime(d["Дата сделки"], format="%d.%m.%Y")
d = d.merge(c[["Номер контракта", "Валюта", "Код ТН ВЭД"]], on="Номер контракта").merge(u, left_on="dt", right_on="Дата")
d["amt"] = num(d["Сумма сделки"]); d["vol"] = num(d["Количество"]) * num(d["Лот"])
d["uzs"] = np.where(d["Валюта"] == "Доллар США", d["amt"] * d["Курс"], d["amt"])

def sql(q): return ds.run_sql(q)["rows"]
checks = []
def chk(name, db, ref, tol=1e-6):
    ok = abs(db - ref) <= tol * max(1, abs(ref)); checks.append(ok)
    print(("OK  " if ok else "FAIL"), name, db, ref)

chk("всего сделок", sql("select count(*) from deals")[0][0], len(d))
chk("сумма, сум", sql("select sum(amount_uzs) from deals")[0][0], d.uzs.sum())
for y in (2022, 2025):
    chk(f"сделок {y}", sql(f"select count(*) from deals where year={y}")[0][0], (d.dt.dt.year == y).sum())
chk("экспорт USD", sql("select sum(amount) from deals where is_export=1")[0][0], d[d["Валюта"] == "Доллар США"].amt.sum())
chk("аннулировано", sql("select sum(is_annulled) from deals")[0][0], (d["Состояние сделки"] == "Аннулирован(Не оплачен)").sum())
cot = d[d["Код ТН ВЭД"] == "520100"]
chk("хлопок-сырец, сделок", sql("select count(*) from deals where product_code='520100'")[0][0], len(cot))
chk("хлопок-сырец, объём кг", sql("select sum(volume) from deals where product_code='520100'")[0][0], cot.vol.sum())
chk("хлопок через LIKE по сырому названию", sql("select count(*) from deals where lower(product_raw) like '%хлопок%сырец%' or lower(product_raw) like '%хлопок-сырец%'")[0][0], len(cot))
top = d.groupby("ИНН продавца").uzs.sum().sort_values(ascending=False)
r = sql("select seller_inn, sum(amount_uzs) s from deals group by 1 order by 2 desc limit 1")[0]
chk("топ-продавец сумма", r[1], top.iloc[0]); assert r[0] == top.index[0]; print("OK   топ-продавец ИНН", r[0])
reg = d.groupby("Регион").uzs.sum().sort_values(ascending=False)
r = sql("select region, sum(amount_uzs) from deals group by 1 order by 2 desc limit 1")[0]
chk("топ-регион сумма", r[1], reg.iloc[0]); assert r[0] == reg.index[0]
assert all(checks), "есть расхождения!"
print(f"\nВсе {len(checks)} проверок пройдены")

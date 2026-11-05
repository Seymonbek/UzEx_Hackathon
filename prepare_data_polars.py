"""Собирает чистую SQLite-базу uzex.db из CSV с использованием Polars (высокая скорость, без pandas).

Запуск:
    python prepare_data_polars.py --data .. --out uzex.db
"""
import argparse
import glob
import os
import re
import sqlite3
import sys
import tempfile
import time
import zipfile
import polars as pl

sys.stdout.reconfigure(encoding="utf-8")

# Импортируем справочники и функции нормализации
from catalog import PRODUCTS, REGIONS
from textnorm import norm_name, norm_sort, norm_class, clean_variant, norm_text


def find_dir(path):
    if path.lower().endswith(".zip"):
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        path = tmp
    for root, _, files in os.walk(path):
        if "contracts.csv" in files:
            return root
    raise SystemExit("contracts.csv не найден в " + path)


def clean_num_str(s: str) -> float | None:
    if s is None or s == "":
        return None
    val = re.sub(r"[\s\u00a0]", "", str(s))
    try:
        return float(val)
    except ValueError:
        return None


def parse_dmy_to_iso(date_str: str) -> str | None:
    if not date_str:
        return None
    parts = date_str.split(".")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str


def build(data_path, out_db):
    t0 = time.time()
    data_dir = find_dir(data_path)
    print(f"[{time.strftime('%H:%M:%S')}] Считывание данных из {data_dir}...")

    # 1. Справочники
    reg_rows = []
    for r in REGIONS:
        reg_rows.append({
            "region": r[0],
            "region_contract_ru": r[1],
            "region_ru": r[2],
            "region_uz": r[3],
            "region_key": norm_text(r[3])
        })
    df_reg = pl.DataFrame(reg_rows)

    prod_rows = [
        {"product_code": k, "product_ru": v[0], "product_uz": v[1]}
        for k, v in PRODUCTS.items()
    ]
    df_prod = pl.DataFrame(prod_rows)

    # 2. Participants
    df_parts = pl.read_csv(os.path.join(data_dir, "participants.csv"))
    df_parts = df_parts.rename({
        "ИНН": "inn",
        "Наименование": "name",
        "Регион": "region",
        "Вид деятельности": "activity",
        "Роль": "role",
        "Плательщик НДС": "vat_payer"
    })
    df_parts = df_parts.with_columns([
        pl.col("inn").cast(pl.String),
        pl.col("name").map_elements(norm_name, return_dtype=pl.String).alias("name_norm")
    ])

    # 3. Brokers
    df_brokers = pl.read_csv(os.path.join(data_dir, "brokers.csv"))
    df_brokers = df_brokers.rename({
        "Код брокера": "broker_code",
        "Наименование": "name",
        "ИНН": "inn",
        "Регион": "region"
    })
    df_brokers = df_brokers.with_columns([
        pl.col("inn").cast(pl.String),
        pl.col("name").map_elements(norm_name, return_dtype=pl.String).alias("name_norm")
    ])

    # 4. USD rates
    df_usd_raw = pl.read_csv(os.path.join(data_dir, "usd_rates.csv"))
    df_usd = df_usd_raw.select([
        pl.col("Дата").str.strptime(pl.Date, format="%d.%m.%Y").dt.to_string("%Y-%m-%d").alias("date"),
        pl.col("Курс").cast(pl.Float64).alias("rate")
    ])

    # 5. Contracts
    df_c_raw = pl.read_csv(os.path.join(data_dir, "contracts.csv"), infer_schema_length=5000)
    
    # helper for clean numeric
    df_c = df_c_raw.select([
        pl.col("Номер контракта").cast(pl.Int64).alias("contract_id"),
        pl.col("Наименование продукта").alias("product_contract_name"),
        pl.col("Наименование продукта").map_elements(clean_variant, return_dtype=pl.String).alias("product_variant"),
        pl.col("Код ТН ВЭД").cast(pl.String).alias("product_code"),
        pl.col("Группа товара").alias("product_group"),
        pl.col("Категория товара").alias("category"),
        pl.col("Отрасль промышленности").alias("industry"),
        pl.col("Единица измерения").alias("unit"),
        pl.col("Лот").cast(pl.Float64).alias("lot"),
        pl.when(pl.col("Валюта") == "Доллар США").then(pl.lit("USD")).otherwise(pl.lit("UZS")).alias("currency"),
        pl.col("Базисная цена").cast(pl.Float64).alias("basis_price"),
        pl.col("Сумма залога").str.replace_all(r"[^\d.]", "").cast(pl.Float64).alias("deposit_pct"),
        pl.col("Базис поставки").alias("delivery_basis"),
        pl.col("Упаковка").alias("packaging"),
        pl.col("Регион").alias("warehouse_region_ru"),
        pl.col("Адрес склада").alias("warehouse_address"),
        pl.col("Тип торгов").alias("trade_type"),
        pl.col("Тип контракта").alias("contract_type"),
        pl.col("Форма контракта").alias("contract_form"),
        pl.col("Срок оплаты").cast(pl.Int64).alias("pay_term_days"),
        pl.col("Срок поставки").cast(pl.Int64).alias("delivery_term_days"),
        pl.col("ИНН продавца").cast(pl.String).alias("seller_inn"),
        pl.col("Дата регистрации").str.strptime(pl.Date, format="%d.%m.%Y").dt.to_string("%Y-%m-%d").alias("registered"),
        pl.col("Действует до").str.strptime(pl.Date, format="%d.%m.%Y").dt.to_string("%Y-%m-%d").alias("valid_until"),
    ])
    df_c = df_c.join(df_prod.select(["product_code", "product_ru"]), on="product_code", how="left")

    print(f"[{time.strftime('%H:%M:%S')}] Считывание сделок (deals_2022..2026)...")
    deal_files = sorted(glob.glob(os.path.join(data_dir, "deals_*.csv")))
    
    # We read deals with Polars
    deals_dfs = []
    for f in deal_files:
        df_one = pl.read_csv(f, infer_schema_length=5000, schema_overrides={
            "Номер сделки": pl.Int64,
            "Количество": pl.String,
            "Лот": pl.String,
            "Сумма сделки": pl.String,
            "Стартовая цена": pl.String,
            "Номер контракта": pl.Int64,
            "ИНН продавца": pl.String,
            "ИНН покупателя": pl.String,
            "Поставлено": pl.String,
        })
        deals_dfs.append(df_one)
    
    df_deals_raw = pl.concat(deals_dfs)
    print(f"[{time.strftime('%H:%M:%S')}] Всего загружено сделок: {len(df_deals_raw):,}. Обработка и нормализация...")

    # Чистим числовые поля от пробелов
    clean_num_expr = lambda col_name: (
        pl.col(col_name)
        .str.replace_all(r"[\s\u00a0]", "")
        .cast(pl.Float64, strict=False)
    )

    df_d = df_deals_raw.select([
        pl.col("Номер сделки").cast(pl.Int64).alias("deal_id"),
        pl.col("Дата сделки").str.strptime(pl.Date, format="%d.%m.%Y").alias("deal_date_dt"),
        pl.col("Время сделки").alias("deal_time"),
        pl.col("Тип торгов").alias("trade_type"),
        clean_num_expr("Количество").alias("quantity_lots"),
        clean_num_expr("Лот").alias("lot_size"),
        clean_num_expr("Сумма сделки").alias("amount"),
        clean_num_expr("Стартовая цена").alias("start_price"),
        pl.col("Номер контракта").cast(pl.Int64).alias("contract_id"),
        pl.col("Наименование товара").alias("product_raw"),
        pl.col("Единица измерения").alias("unit"),
        pl.col("Регион").alias("region"),
        pl.col("Тип контракта").alias("contract_type"),
        pl.col("Форма контракта").alias("contract_form"),
        pl.col("Состояние сделки").alias("state"),
        pl.col("ИНН продавца").alias("seller_inn"),
        pl.col("ИНН покупателя").alias("buyer_inn"),
        pl.col("Брокер продавца").alias("seller_broker"),
        pl.col("Брокер покупателя").alias("buyer_broker"),
        pl.col("Дата оплаты").str.strptime(pl.Date, format="%d.%m.%Y", strict=False).alias("pay_date_dt"),
        pl.col("Дата поставки").str.strptime(pl.Date, format="%d.%m.%Y", strict=False).alias("deliver_date_dt"),
        clean_num_expr("Поставлено").alias("delivered_lots"),
    ])

    # Join contracts attributes
    contracts_meta = df_c.select([
        "contract_id", "currency", "product_code", "product_ru", "product_variant",
        "category", "product_group", "industry", "basis_price", "pay_term_days", "delivery_term_days"
    ])
    df_d = df_d.join(contracts_meta, on="contract_id", how="left")

    # Join USD rate
    df_usd_prep = df_usd.with_columns(pl.col("date").str.strptime(pl.Date, format="%Y-%m-%d").alias("deal_date_dt"))
    df_d = df_d.join(df_usd_prep.select(["deal_date_dt", "rate"]), on="deal_date_dt", how="left")
    df_d = df_d.rename({"rate": "usd_rate"})

    # Computations
    print(f"[{time.strftime('%H:%M:%S')}] Расчет агрегатов, цен, объемов...")
    df_d = df_d.with_columns([
        (pl.col("quantity_lots") * pl.col("lot_size")).alias("volume"),
    ])

    df_d = df_d.with_columns([
        (pl.col("amount") / pl.col("volume")).alias("unit_price"),
        pl.when(pl.col("currency") == "USD")
          .then(pl.col("amount") * pl.col("usd_rate"))
          .otherwise(pl.col("amount"))
          .alias("amount_uzs"),
        pl.when(pl.col("currency") == "USD")
          .then(pl.col("amount"))
          .otherwise(pl.col("amount") / pl.col("usd_rate"))
          .alias("amount_usd"),
        (pl.col("delivered_lots") * pl.col("lot_size")).alias("delivered_volume"),
        pl.col("deal_date_dt").dt.year().alias("year"),
        pl.col("deal_date_dt").dt.month().alias("month"),
        pl.col("deal_date_dt").dt.quarter().alias("quarter"),
        pl.when(pl.col("state") == "Аннулирован(Не оплачен)").then(1).otherwise(0).alias("is_annulled"),
        pl.when(pl.col("pay_date_dt").is_not_null()).then(1).otherwise(0).alias("is_paid"),
        pl.when(pl.col("state") == "Исполнен").then(1).otherwise(0).alias("is_delivered_full"),
        pl.when(pl.col("contract_type") == "Экспортный").then(1).otherwise(0).alias("is_export"),
        ((pl.col("pay_date_dt") - pl.col("deal_date_dt")).dt.total_days()).alias("pay_days"),
        ((pl.col("deliver_date_dt") - pl.col("pay_date_dt")).dt.total_days()).alias("delivery_days"),
    ])

    df_d = df_d.with_columns([
        (pl.col("amount_uzs") / pl.col("volume")).alias("unit_price_uzs"),
        ((pl.col("unit_price") / pl.col("start_price") - 1.0) * 100.0).alias("price_vs_start_pct"),
        ((pl.col("unit_price") / pl.col("basis_price") - 1.0) * 100.0).alias("price_vs_basis_pct"),
        (pl.col("delivery_days") - pl.col("delivery_term_days")).fill_null(0).clip(lower_bound=0).alias("delivery_late_days"),
    ])

    df_d = df_d.with_columns([
        pl.when(pl.col("deliver_date_dt").is_not_null() & (pl.col("delivery_late_days") > 0))
          .then(1)
          .otherwise(0)
          .alias("is_delivery_late"),
        pl.col("product_raw").map_elements(norm_sort, return_dtype=pl.String).alias("sort_norm"),
        pl.col("product_raw").map_elements(norm_class, return_dtype=pl.String).alias("class_norm"),
        pl.col("deal_date_dt").dt.to_string("%Y-%m-%d").alias("deal_date"),
        pl.col("pay_date_dt").dt.to_string("%Y-%m-%d").alias("pay_date"),
        pl.col("deliver_date_dt").dt.to_string("%Y-%m-%d").alias("deliver_date"),
    ])

    df_d = df_d.drop(["deal_date_dt", "pay_date_dt", "deliver_date_dt", "basis_price", "pay_term_days", "delivery_term_days", "usd_rate"])
    df_d = df_d.sort("deal_id")

    # 6. Запись в SQLite
    print(f"[{time.strftime('%H:%M:%S')}] Экспорт в SQLite базу: {out_db}...")
    if os.path.exists(out_db):
        try:
            os.remove(out_db)
        except Exception:
            pass

    con = sqlite3.connect(out_db)
    
    # PyPolars to SQL directly or via chunks
    # We can write directly via sqlite3 executemany
    print("Запись таблицы participants...")
    df_parts.to_pandas().to_sql("participants", con, index=False) if False else None # fallback
    
    # Generic fast writer using sqlite3 executemany
    def write_polars_to_sqlite(df: pl.DataFrame, table_name: str, conn: sqlite3.Connection):
        cols = df.columns
        placeholders = ",".join(["?"] * len(cols))
        col_defs = ", ".join([f'"{c}" TEXT' for c in cols]) # SQLite is dynamically typed
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')
        rows = df.iter_rows()
        # insert in chunks of 50,000
        batch = []
        for r in rows:
            batch.append(r)
            if len(batch) >= 50000:
                conn.executemany(f'INSERT INTO "{table_name}" VALUES ({placeholders})', batch)
                batch = []
        if batch:
            conn.executemany(f'INSERT INTO "{table_name}" VALUES ({placeholders})', batch)
        conn.commit()

    write_polars_to_sqlite(df_parts, "participants", con)
    write_polars_to_sqlite(df_brokers, "brokers", con)
    write_polars_to_sqlite(df_usd, "usd_rates", con)
    write_polars_to_sqlite(df_reg, "regions", con)
    write_polars_to_sqlite(df_prod, "products", con)
    write_polars_to_sqlite(df_c, "contracts", con)
    print(f"[{time.strftime('%H:%M:%S')}] Запись 500 000 строк deals...")
    write_polars_to_sqlite(df_d, "deals", con)

    print(f"[{time.strftime('%H:%M:%S')}] Создание индексов...")
    for ix in ["deal_date", "product_code", "seller_inn", "buyer_inn", "region", "contract_id", "year"]:
        con.execute(f'CREATE INDEX IF NOT EXISTS ix_deals_{ix} ON deals("{ix}")')
    con.execute('CREATE INDEX IF NOT EXISTS ix_part_inn ON participants("inn")')
    con.execute('CREATE INDEX IF NOT EXISTS ix_br_code ON brokers("broker_code")')

    print(f"[{time.strftime('%H:%M:%S')}] Создание представления v_deals...")
    con.execute("""
    CREATE VIEW IF NOT EXISTS v_deals AS
    SELECT d.*,
           r.region_ru, r.region_uz,
           s.name AS seller_name, s.activity AS seller_activity, s.vat_payer AS seller_vat,
           b.name AS buyer_name,  b.activity AS buyer_activity,  b.vat_payer AS buyer_vat, b.region AS buyer_region,
           sb.name AS seller_broker_name, bb.name AS buyer_broker_name
    FROM deals d
    LEFT JOIN regions r ON r.region = d.region
    LEFT JOIN participants s ON s.inn = d.seller_inn
    LEFT JOIN participants b ON b.inn = d.buyer_inn
    LEFT JOIN brokers sb ON sb.broker_code = d.seller_broker
    LEFT JOIN brokers bb ON bb.broker_code = d.buyer_broker
    """)
    con.commit()
    print(f"[{time.strftime('%H:%M:%S')}] Оптимизация (VACUUM)...")
    con.execute("VACUUM")
    con.close()

    elapsed = time.time() - t0
    size_mb = os.path.getsize(out_db) / (1024 * 1024)
    print(f"✅ УСПЕХ: База {out_db} ({size_mb:.1f} МБ) успешно собрана за {elapsed:.1f} сек!")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="..")
    ap.add_argument("--out", default="uzex.db")
    args = ap.parse_args()
    build(args.data, args.out)


if __name__ == "__main__":
    main()

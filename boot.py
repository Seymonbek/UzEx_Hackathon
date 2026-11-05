"""Гарантирует загрузку .env и наличие базы: если uzex.db нет — собирает её из CSV/ZIP (≈30 с)."""
import os
from dotenv import load_dotenv

here = os.path.dirname(os.path.abspath(__file__))
# Загружаем .env из текущей папки или родительской
load_dotenv(os.path.join(here, ".env"))
load_dotenv(os.path.join(os.path.dirname(here), ".env"))

import datastore as ds

def ensure_db():
    if os.path.exists(ds.DB_PATH):
        return
    import prepare_data_polars as prepare_data
    parent = os.path.dirname(here)
    for cand in (os.environ.get("UZEX_DATA"), os.path.join(here, "uzex_spot_data.zip"),
                 parent, os.path.join(here, "data"), os.path.join(here, "uzex_spot_data")):
        if cand and os.path.exists(cand):
            prepare_data.build(cand, ds.DB_PATH)
            return
    raise SystemExit("Нет базы uzex.db и исходных данных. Положите uzex_spot_data.zip рядом или задайте UZEX_DATA.")

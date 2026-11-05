"""Собирает чистую SQLite-базу uzex.db из CSV (500 000 сделок).
Использует быстрый Polars ETL движок.
"""
import prepare_data_polars

if __name__ == "__main__":
    prepare_data_polars.main()

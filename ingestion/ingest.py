import os
import logging
import pandas as pd
import psycopg2
from io import StringIO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.environ.get(
    "RAW_DATA_DIR",
    os.path.join(_here, "..", "data", "raw"),
)

SCHEMA = "staging"

DATE_COLS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
}

FORCE_STR = {
    "customers": ["customer_zip_code_prefix"],
}

FILE_TABLE_MAP = {
    "olist_orders_dataset.csv":         "orders",
    "olist_customers_dataset.csv":      "customers",
    "olist_products_dataset.csv":       "products",
    "olist_order_items_dataset.csv":    "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def pg_type(dtype) -> str:
    """Map a pandas dtype to a PostgreSQL column type."""
    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    if pd.api.types.is_float_dtype(dtype):
        return "DOUBLE PRECISION"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP"
    if pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    return "TEXT"


def read_csv(filepath: str, table: str) -> pd.DataFrame:
    df = pd.read_csv(
        filepath,
        parse_dates=DATE_COLS.get(table, []),
        dtype={col: str for col in FORCE_STR.get(table, [])},
    )
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def write_staging(df: pd.DataFrame, table: str) -> None:
    """
    Drop-and-recreate pattern (idempotent).
    Uses COPY FROM STDIN — orders of magnitude faster than row-by-row INSERT.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS {SCHEMA}."{table}" CASCADE')

            col_defs = ", ".join(
                f'"{col}" {pg_type(dtype)}' for col, dtype in df.dtypes.items()
            )
            cur.execute(f'CREATE TABLE {SCHEMA}."{table}" ({col_defs})')

            buf = StringIO()
            df.to_csv(buf, index=False, header=False, na_rep="\\N")
            buf.seek(0)
            cur.copy_expert(
                f"COPY {SCHEMA}.\"{table}\" FROM STDIN WITH (FORMAT CSV, NULL '\\N')",
                buf,
            )
        conn.commit()
    finally:
        conn.close()


# ── Entry point ────────────────────────────────────────────────────────────────

def run() -> None:
    for csv_file, table in FILE_TABLE_MAP.items():
        fpath = os.path.normpath(os.path.join(RAW_DIR, csv_file))
        if not os.path.isfile(fpath):
            log.warning("Not found, skipping: %s", fpath)
            continue

        log.info("%-44s → %s.%s", csv_file, SCHEMA, table)
        df = read_csv(fpath, table)
        write_staging(df, table)
        log.info("  %d rows, %d columns", len(df), len(df.columns))

    log.info("Done.")


if __name__ == "__main__":
    run()

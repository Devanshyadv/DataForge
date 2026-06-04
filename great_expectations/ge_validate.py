"""
Data quality validation using Pandera.

great-expectations 0.18.x is incompatible with Python 3.12 (pydantic v1 issue).
Pandera provides the same DQ concepts — column nullability, uniqueness, value
ranges, categorical checks — with full Python 3.12 support.

The JSON expectation files in ./expectations/ document the rules; this script
is the executable implementation.
"""

import os
import logging
import psycopg2
import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema, Check

log = logging.getLogger(__name__)

_VALID_STATUSES = [
    "delivered", "shipped", "canceled", "unavailable",
    "processing", "created", "approved", "invoiced",
]
_VALID_PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card", "not_defined"]

# ── Pandera schemas ────────────────────────────────────────────────────────────

SCHEMAS: dict[str, DataFrameSchema] = {

    "staging_orders": DataFrameSchema(
        columns={
            "order_id":    Column(nullable=False, unique=True),
            "customer_id": Column(nullable=False),
            "order_status": Column(
                nullable=False,
                checks=Check.isin(_VALID_STATUSES),
            ),
        },
        checks=Check(lambda df: len(df) > 0, error="staging.orders is empty"),
        coerce=True,
    ),

    "staging_order_items": DataFrameSchema(
        columns={
            "order_id":      Column(nullable=False),
            "product_id":    Column(nullable=False),
            "price":         Column(float, nullable=False, checks=Check.ge(0)),
            "freight_value": Column(float, nullable=False, checks=Check.ge(0)),
        },
        checks=Check(lambda df: len(df) > 0, error="staging.order_items is empty"),
        coerce=True,
    ),

    "staging_order_payments": DataFrameSchema(
        columns={
            "order_id":      Column(nullable=False),
            "payment_value": Column(float, nullable=False, checks=Check.ge(0)),
            "payment_type":  Column(nullable=False, checks=Check.isin(_VALID_PAYMENT_TYPES)),
        },
        checks=Check(lambda df: len(df) > 0, error="staging.order_payments is empty"),
        coerce=True,
    ),
}

VALIDATIONS = [
    {
        "name":  "staging_orders",
        "query": "SELECT order_id, customer_id, order_status FROM staging.orders",
    },
    {
        "name":  "staging_order_items",
        "query": "SELECT order_id, product_id, price, freight_value FROM staging.order_items",
    },
    {
        "name":  "staging_order_payments",
        "query": "SELECT order_id, payment_value, payment_type FROM staging.order_payments",
    },
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_conn():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def _fetch(conn, query: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


# ── Entry point ────────────────────────────────────────────────────────────────

def validate_all() -> None:
    conn = _get_conn()
    failures = []

    try:
        for v in VALIDATIONS:
            df = _fetch(conn, v["query"])
            try:
                SCHEMAS[v["name"]].validate(df, lazy=True)
                log.info("PASS  %-32s  %d rows", v["name"], len(df))
            except pa.errors.SchemaErrors as exc:
                log.error("FAIL  %s:", v["name"])
                for _, row in exc.failure_cases.iterrows():
                    log.error(
                        "      check=%-45s  col=%-20s  value=%s",
                        row.get("check", ""),
                        row.get("column", ""),
                        row.get("failure_case", ""),
                    )
                failures.append(v["name"])
    finally:
        conn.close()

    if failures:
        raise ValueError(f"DQ validation failed for: {failures}")

    log.info("All DQ validations passed.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    validate_all()

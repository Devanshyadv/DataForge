"""
dataforge_pipeline — daily ELT orchestration for the Olist dataset

Task flow:
    ingest_raw  →  dbt_run  →  dbt_test  →  data_quality_check
"""

import os
import logging
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

sys.path.insert(0, "/opt/airflow")

log = logging.getLogger(__name__)

_DBT_BASE = (
    "/home/airflow/.local/bin/dbt {cmd} "
    "--profiles-dir /opt/airflow/dbt "
    "--project-dir /opt/airflow/dbt "
    "--log-path /tmp/dbt_logs "
    "--target-path /tmp/dbt_target"
)


# ── Task callables ─────────────────────────────────────────────────────────────

def _ingest(**ctx):
    from ingestion.ingest import run
    run()


def _dq_check(**ctx):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ge_validate",
        "/opt/airflow/great_expectations/ge_validate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.validate_all()


# ── DAG ───────────────────────────────────────────────────────────────────────

default_args = {
    "owner": "dataforge",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
    "email_on_retry": False,
}

with DAG(
    dag_id="dataforge_pipeline",
    description="Olist ELT: ingest → dbt run → dbt test → DQ check",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["dataforge", "olist", "elt"],
) as dag:

    ingest_raw = PythonOperator(
        task_id="ingest_raw",
        python_callable=_ingest,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=_DBT_BASE.format(cmd="run"),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=_DBT_BASE.format(cmd="test"),
    )

    data_quality_check = PythonOperator(
        task_id="data_quality_check",
        python_callable=_dq_check,
    )

    ingest_raw >> dbt_run >> dbt_test >> data_quality_check

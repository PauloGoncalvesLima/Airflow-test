# fmt: off
# ruff: noqa

from airflow import DAG
from airflow.datasets import Dataset
from airflow.models import Variable
from airflow.operators.bash_operator import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.dates import days_ago
from plugins.telegram.callbacks import send_telegram

from datetime import timedelta

default_args = {
    'owner': 'DBT-Genrated',
    'retries': 2,
    'retry_delay': timedelta(minutes=30),
    'pool': 'dbt_pool'
}

with DAG(
    "run_model__dates",
    default_args=default_args,
    schedule=[Dataset('bronze_dates')],
    start_date=days_ago(1),
    tags=["dbt", "model"],
    max_active_runs=1,
    on_success_callback=None,
    on_failure_callback=send_telegram,
) as dag:

    end_task = EmptyOperator(
        task_id="end",
        outlets=[Dataset("dates_model")],
    )

    dates_task = BashOperator(
        task_id='run_dates',
        bash_command='rm -r /tmp/dbt_run_dates || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_run_dates \
&& cd /tmp/dbt_run_dates \
&& dbt deps && dbt run --select dates \
&& rm -r /tmp/dbt_run_dates',
        env={
            'DBT_POSTGRES_HOST': Variable.get("bp_dw_pg_host"),
            'DBT_POSTGRES_USER': Variable.get("bp_dw_pg_user"),
            'DBT_POSTGRES_PASSWORD': Variable.get("bp_dw_pg_password"),
            'DBT_POSTGRES_ENVIRONMENT': Variable.get("bp_dw_pg_environment"),
            'DBT_POSTGRES_PORT': Variable.get("bp_dw_pg_port"),
            'DBT_POSTGRES_DATABASE': Variable.get("bp_dw_pg_db"),
        },
        append_env=True
    )

    dates_task >> end_task

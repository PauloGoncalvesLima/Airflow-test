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
    "run_model__device_entry_channel",
    default_args=default_args,
    schedule=[Dataset('visits_model'), Dataset('dates_model')],
    start_date=days_ago(1),
    tags=["dbt", "model"],
    max_active_runs=1,
    on_success_callback=None,
    on_failure_callback=send_telegram,
) as dag:

    end_task = EmptyOperator(
        task_id="end",
        outlets=[Dataset("device_entry_channel_model")],
    )

    device_entry_channel_task = BashOperator(
        task_id='run_device_entry_channel',
        bash_command='rm -r /tmp/dbt_run_device_entry_channel || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_run_device_entry_channel \
&& cd /tmp/dbt_run_device_entry_channel \
&& dbt deps && dbt run --select device_entry_channel \
&& rm -r /tmp/dbt_run_device_entry_channel',
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

    not_null_device_entry_channel_day_task = BashOperator(
        task_id='test_not_null_device_entry_channel_day',
        bash_command='rm -r /tmp/dbt_test_not_null_device_entry_channel_day || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_device_entry_channel_day \
&& cd /tmp/dbt_test_not_null_device_entry_channel_day \
&& dbt deps && dbt test --select not_null_device_entry_channel_day \
&& rm -r /tmp/dbt_test_not_null_device_entry_channel_day',
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

    not_null_device_entry_channel_entry_channel_task = BashOperator(
        task_id='test_not_null_device_entry_channel_entry_channel',
        bash_command='rm -r /tmp/dbt_test_not_null_device_entry_channel_entry_channel || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_device_entry_channel_entry_channel \
&& cd /tmp/dbt_test_not_null_device_entry_channel_entry_channel \
&& dbt deps && dbt test --select not_null_device_entry_channel_entry_channel \
&& rm -r /tmp/dbt_test_not_null_device_entry_channel_entry_channel',
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

    not_null_device_entry_channel_device_task = BashOperator(
        task_id='test_not_null_device_entry_channel_device',
        bash_command='rm -r /tmp/dbt_test_not_null_device_entry_channel_device || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_device_entry_channel_device \
&& cd /tmp/dbt_test_not_null_device_entry_channel_device \
&& dbt deps && dbt test --select not_null_device_entry_channel_device \
&& rm -r /tmp/dbt_test_not_null_device_entry_channel_device',
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

    not_null_device_entry_channel_unique_visitors_task = BashOperator(
        task_id='test_not_null_device_entry_channel_unique_visitors',
        bash_command='rm -r /tmp/dbt_test_not_null_device_entry_channel_unique_visitors || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_device_entry_channel_unique_visitors \
&& cd /tmp/dbt_test_not_null_device_entry_channel_unique_visitors \
&& dbt deps && dbt test --select not_null_device_entry_channel_unique_visitors \
&& rm -r /tmp/dbt_test_not_null_device_entry_channel_unique_visitors',
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

    not_null_device_entry_channel_avg_visit_time_in_minutes_task = BashOperator(
        task_id='test_not_null_device_entry_channel_avg_visit_time_in_minutes',
        bash_command='rm -r /tmp/dbt_test_not_null_device_entry_channel_avg_visit_time_in_minutes || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_device_entry_channel_avg_visit_time_in_minutes \
&& cd /tmp/dbt_test_not_null_device_entry_channel_avg_visit_time_in_minutes \
&& dbt deps && dbt test --select not_null_device_entry_channel_avg_visit_time_in_minutes \
&& rm -r /tmp/dbt_test_not_null_device_entry_channel_avg_visit_time_in_minutes',
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

    device_entry_channel_task >> not_null_device_entry_channel_day_task >> end_task
    device_entry_channel_task >> not_null_device_entry_channel_entry_channel_task >> end_task
    device_entry_channel_task >> not_null_device_entry_channel_device_task >> end_task
    device_entry_channel_task >> not_null_device_entry_channel_unique_visitors_task >> end_task
    device_entry_channel_task >> not_null_device_entry_channel_avg_visit_time_in_minutes_task >> end_task

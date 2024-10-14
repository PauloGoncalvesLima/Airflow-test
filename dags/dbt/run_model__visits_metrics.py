# fmt: off
# ruff: noqa

from airflow import DAG
from airflow.datasets import Dataset
from airflow.models import Variable
from airflow.operators.bash_operator import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.dates import days_ago

from datetime import timedelta

default_args = {
    'owner': 'DBT-Genrated',
    'retries': 2,
    'retry_delay': timedelta(minutes=30),
    'pool': 'dbt_pool'
}

with DAG(
    "run_model__visits_metrics",
    default_args=default_args,
    schedule=[Dataset('visits_model'), Dataset('users_model'), Dataset('dates_model')],
    start_date=days_ago(1),
    tags=["dbt", "model"],
    max_active_runs=1
) as dag:

    end_task = EmptyOperator(
        task_id="end",
        outlets=[Dataset("visits_metrics_model")],
    )

    visits_metrics_task = BashOperator(
        task_id='run_visits_metrics',
        bash_command='rm -r /tmp/dbt_run_visits_metrics || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_run_visits_metrics \
&& cd /tmp/dbt_run_visits_metrics \
&& dbt deps && dbt run --select visits_metrics \
&& rm -r /tmp/dbt_run_visits_metrics',
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

    not_null_visits_metrics_date_day_task = BashOperator(
        task_id='test_not_null_visits_metrics_date_day',
        bash_command='rm -r /tmp/dbt_test_not_null_visits_metrics_date_day || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_visits_metrics_date_day \
&& cd /tmp/dbt_test_not_null_visits_metrics_date_day \
&& dbt deps && dbt test --select not_null_visits_metrics_date_day \
&& rm -r /tmp/dbt_test_not_null_visits_metrics_date_day',
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

    unique_visits_metrics_date_day_task = BashOperator(
        task_id='test_unique_visits_metrics_date_day',
        bash_command='rm -r /tmp/dbt_test_unique_visits_metrics_date_day || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_unique_visits_metrics_date_day \
&& cd /tmp/dbt_test_unique_visits_metrics_date_day \
&& dbt deps && dbt test --select unique_visits_metrics_date_day \
&& rm -r /tmp/dbt_test_unique_visits_metrics_date_day',
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

    not_null_visits_metrics_visitor_count_task = BashOperator(
        task_id='test_not_null_visits_metrics_visitor_count',
        bash_command='rm -r /tmp/dbt_test_not_null_visits_metrics_visitor_count || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_visits_metrics_visitor_count \
&& cd /tmp/dbt_test_not_null_visits_metrics_visitor_count \
&& dbt deps && dbt test --select not_null_visits_metrics_visitor_count \
&& rm -r /tmp/dbt_test_not_null_visits_metrics_visitor_count',
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

    not_null_visits_metrics_user_count_task = BashOperator(
        task_id='test_not_null_visits_metrics_user_count',
        bash_command='rm -r /tmp/dbt_test_not_null_visits_metrics_user_count || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_visits_metrics_user_count \
&& cd /tmp/dbt_test_not_null_visits_metrics_user_count \
&& dbt deps && dbt test --select not_null_visits_metrics_user_count \
&& rm -r /tmp/dbt_test_not_null_visits_metrics_user_count',
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

    not_null_visits_metrics_visit_time_spend_in_minutes_task = BashOperator(
        task_id='test_not_null_visits_metrics_visit_time_spend_in_minutes',
        bash_command='rm -r /tmp/dbt_test_not_null_visits_metrics_visit_time_spend_in_minutes || true \
&& cp -r /opt/airflow/dags-config/repo/plugins/dbt_pg_project /tmp/dbt_test_not_null_visits_metrics_visit_time_spend_in_minutes \
&& cd /tmp/dbt_test_not_null_visits_metrics_visit_time_spend_in_minutes \
&& dbt deps && dbt test --select not_null_visits_metrics_visit_time_spend_in_minutes \
&& rm -r /tmp/dbt_test_not_null_visits_metrics_visit_time_spend_in_minutes',
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

    visits_metrics_task >> not_null_visits_metrics_date_day_task >> end_task
    visits_metrics_task >> unique_visits_metrics_date_day_task >> end_task
    visits_metrics_task >> not_null_visits_metrics_visitor_count_task >> end_task
    visits_metrics_task >> not_null_visits_metrics_user_count_task >> end_task
    visits_metrics_task >> not_null_visits_metrics_visit_time_spend_in_minutes_task >> end_task

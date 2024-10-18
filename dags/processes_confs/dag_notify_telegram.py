import logging

from airflow.models import Variable
from airflow.decorators import dag, task
from airflow.providers.telegram.hooks.telegram import TelegramHook
from airflow.operators.empty import EmptyOperator
from datetime import datetime, timedelta
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

default_args = {
    "owner": "Eric Silveira",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

TELEGRAM_CONN_ID = "telegram_decidim"
SCHEMA = "public"
POSTGRES_CONN = "postgres_conn"
TABLE = 'teste'
VARIABLE = 'registry_numbers'

@dag(
    tags=['automation', 'telegram', 'notify'],
    schedule_interval="10 */1 * * *",
    start_date=datetime(2023, 11, 18),
    catchup=False,
    default_args=default_args,
)
def automation_notify_telegram():

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    @task(task_id='verify_atualization')
    def verify_atualization_db():
        hook = PostgresHook(postgres_conn_id=POSTGRES_CONN)
        connection = hook.get_conn()
        postgres_cursor = connection.cursor()

        count  = Variable.get(VARIABLE, default_var=0)

        query = f"""
            SELECT *
            FROM {SCHEMA}.{TABLE}
            WHERE id > {count}
            ORDER BY id DESC;
        """

        postgres_cursor.execute(query)
        result = postgres_cursor.fetchall()

        return result


    # @task(task_id='teste')
    # def send_telegram_message():
    #     telegram_hook = TelegramHook(telegram_conn_id=TELEGRAM_CONN_ID)
    #     telegram_hook.send_message(
    #         text="This is a test message from Airflow!",
    #         chat_id="<your_telegram_chat_id>",  # Add the chat ID here
    #     )



    start >> verify_atualization_db() >> end

automation_notify_telegram()
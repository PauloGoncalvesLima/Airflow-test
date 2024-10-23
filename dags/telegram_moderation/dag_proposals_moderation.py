from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.ssh.hooks.ssh import SSHHook
from airflow.providers.telegram.hooks.telegram import TelegramHook
from bs4 import BeautifulSoup
from sqlalchemy import create_engine

if TYPE_CHECKING:
    from sshtunnel import SSHTunnelForwarder
import urllib.parse

BP_DB = "bp_replica"
CONFIG_DB = "pg_bp_analytics"

SSH_CONN = "ssh_tunnel_decidim"

TELEGRAM_CONN_ID = "telegram_moderation"

QUERIES_FOLDER = Path(__file__).parent.joinpath("./queries/")
with open(QUERIES_FOLDER.joinpath("./messages_to_send_processes.sql")) as file:
    PROPOSALS_IN_PROCESSES_SQL = file.read()


def _get_sql_engine(db_conn, ssh_tunnel=None):
    db = PostgresHook.get_connection(db_conn)
    if ssh_tunnel:
        tunnel = SSHHook(ssh_tunnel).get_tunnel(remote_host=db.host, remote_port=db.port)
        tunnel.start()
        tunnel: SSHTunnelForwarder
        engine = create_engine(
            f"postgresql://{db.login}:{db.password}@127.0.0.1:{tunnel.local_bind_port}/{db.schema}"
        )
    else:
        connection_string = f"postgresql://{db.login}:{db.password}@{db.host}:{db.port}/{db.schema}"
        engine = create_engine(connection_string)

    return engine


def _get_df_from_sql(query, db_conn, ssh_tunnel=None):
    engine = _get_sql_engine(db_conn, ssh_tunnel)
    table = pd.read_sql(query, engine, dtype=str)
    return table


def _get_proposals(
    process_id: str,
    topic_id: str,
    update_date: str,
):
    sql = PROPOSALS_IN_PROCESSES_SQL.format(
        last_update_time=update_date, processes_id=process_id, body="{body}"
    )

    df = _get_df_from_sql(sql, BP_DB, SSH_CONN)
    df["telegram_topic_id"] = topic_id
    return df.to_csv(index=False)


def _parse_xml(mensage_body: str):
    # Parse the XML data
    soup = BeautifulSoup(mensage_body, "xml")

    # Initialize the Markdown string
    markdown_output = ""

    # Find all <dt> (definition terms) and <dd> (definition descriptions)
    for dt in soup.find_all("dt"):
        # Get the <dd> corresponding to the <dt>
        dd = dt.find_next_sibling("dd")

        if dt and dd:
            # Extract and format as Markdown (bold text and descriptions)
            dt_text = dt.get_text(strip=True).replace("\xa0", " ")  # Replacing non-breaking space if present
            dd_text = dd.get_text(strip=True)

            # Add to Markdown string
            markdown_output += f"## {dt_text}\n**{dd_text}**\n\n"
    print(markdown_output)
    return markdown_output


def _parse_series_xml(series):
    result = []
    for body in series:
        result.append(_parse_xml(body))

    return result


def _send_telegram_notification(telegram_chat_id, telegram_topic_id, message, proposals_body):
    """
    Send a notification message through Telegram.

    Args:
    ----
        telegram_conn_id (str): The connection ID for Telegram.
        telegram_chat_id (str): The chat ID for Telegram.
        telegram_topic_id (str): The topic ID for Telegram.
        message (str): The message to be sent.
    """
    assert isinstance(telegram_chat_id, str)
    assert isinstance(telegram_topic_id, str)
    assert isinstance(message, str)

    msg =  message + proposals_body
    print(msg)

    TelegramHook(
        telegram_conn_id=TELEGRAM_CONN_ID,
        chat_id=telegram_chat_id,
    ).send_message(api_params={"text":msg, "message_thread_id": telegram_topic_id})


DEFAULT_ARGS = {
    "owner": "Paulo G.",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=30),
}


@dag(
    default_args=DEFAULT_ARGS,
    schedule="*/10 * * * *",  # every 10 minutes
    start_date=datetime(2023, 11, 18),
    catchup=False,
    description=__doc__,
    max_active_runs=1,
    tags=["notificação", "bp", "proposals"],
    is_paused_upon_creation=False,
)
def notify_proposals():
    @task
    def get_telegram_channels():
        configured_channels = _get_df_from_sql(
            """select * from "telegram-moderation".telegram_channels
                where telegram_topic_type = 'Propostas';""",
            CONFIG_DB,
            SSH_CONN,
        )
        return configured_channels.to_csv(index=False)

    @task
    def get_telegram_messages(telegram_channels: str):
        channels = pd.read_csv(StringIO(telegram_channels), dtype=str)

        processes = channels.apply(
            lambda row: _get_proposals(
                row["participatory_space_id"], row["telegram_topic_id"], row["last_message_sent"]
            ),
            axis=1,
        )

        return processes

    @task
    def send_telegram(processes: list):
        for proposals in processes:
            current_proposals = pd.read_csv(StringIO(proposals), dtype=str)

            mask = current_proposals["body"].str.startswith("<xml>")
            current_proposals.loc[mask, "body"] = current_proposals[mask]["body"].apply(_parse_series_xml)

            current_proposals.apply(
                lambda args: _send_telegram_notification(
                    args["telegram_group_chat_id"],
                    args["telegram_topic_id"],
                    args["telegram_message"],
                    args["body"],
                ),
                axis=1,
            )

    get_telegram_channels_task = get_telegram_channels()
    get_telegram_messages_task = get_telegram_messages(get_telegram_channels_task)
    send_telegram(get_telegram_messages_task)


notify_proposals()

import asyncio
import logging
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.ssh.hooks.ssh import SSHHook
from airflow.providers.telegram.hooks.telegram import TelegramHook
from sqlalchemy import create_engine

from plugins.telegram.decorators import telegram_retry

if TYPE_CHECKING:
    from sshtunnel import SSHTunnelForwarder


BP_DB = "bp_replica"
CONFIG_DB = "pg_bp_analytics"

SSH_CONN = "ssh_tunnel_decidim"

TELEGRAM_CONN_ID = "telegram_moderation"
TELEGRAM_MAX_RETRIES = 10

PROPOSALS_TOPICS_TO_CREATE = {
    "telegram_moderation_proposals_topic_id": lambda name: f"{name}/Propostas",
    "telegram_moderation_comments_topic_id": lambda name: f"{name}/Comentarios Em Propostas",
}

DEFAULT_ARGS = {
    "owner": "Paulo G.",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=30),
}

QUERIES_FOLDER = Path(__file__).parent.joinpath("./queries/")

with open(QUERIES_FOLDER.joinpath("./components_to_moderate.sql")) as file:
    SQL_COMPONENTS_TO_MODERATE = file.read()

TOPICS_TYPES = ["Propostas", "Comentarios em Propostas"]


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


@telegram_retry(max_retries=TELEGRAM_MAX_RETRIES)
def _create_telegram_topic(chat_id: int, name: str):
    if not isinstance(chat_id, int) or not isinstance(name, str):
        logging.error("Chat id: %s\nName: %s", chat_id, name)
        raise TypeError

    logging.info("Chat id: %s\nName: %s", chat_id, name)

    telegram_hook = TelegramHook(telegram_conn_id=TELEGRAM_CONN_ID, chat_id=chat_id)

    new_telegram_topic = asyncio.run(telegram_hook.get_conn().create_forum_topic(chat_id=chat_id, name=name))
    logging.info(type(new_telegram_topic))

    return new_telegram_topic.message_thread_id


@dag(
    dag_id="setup_moderation",
    default_args=DEFAULT_ARGS,
    schedule_interval="10 */1 * * *",
    start_date=datetime(2023, 11, 18),
    catchup=False,
    doc_md=__doc__,
    tags=["creation", "dag", "automation"],
)
def create_telegram_moderation_config():
    @task(multiple_outputs=True)
    def get_components(ssh_tunnel=SSH_CONN):
        components = _get_df_from_sql(SQL_COMPONENTS_TO_MODERATE, BP_DB, ssh_tunnel)

        components_bp = pd.concat(
            [components.assign(telegram_topic_type=topics_type) for topics_type in TOPICS_TYPES],
            ignore_index=True,
        )
        components_bp = components_bp.reset_index(drop=True)

        configured_channels = _get_df_from_sql(
            'select * from "telegram-moderation".telegram_channels;', CONFIG_DB, ssh_tunnel
        )

        components = components_bp.merge(
            configured_channels,
            how="left",
            left_on=["participatory_space_id", "slug", "telegram_group_chat_id", "telegram_topic_type"],
            right_on=["participatory_space_id", "slug", "telegram_group_chat_id", "telegram_topic_type"],
        )

        return {
            "components_to_create_topics": components[components["telegram_topic_id"].isnull()].to_csv(
                index=False
            ),
            "components_to_maintain": components[components["telegram_topic_id"].notnull()].to_csv(
                index=False
            ),
        }

    @task
    def configure_topics(components_to_configure):
        components = pd.read_csv(StringIO(components_to_configure), dtype=str)

        #! TODO: Remover esse filtro
        components = components[components["slug"] == "G20"]
        logging.info(components)

        if components.empty:
            return components.to_csv(index=False)

        components["telegram_topic_id"] = components.apply(
            lambda args: _create_telegram_topic(
                int(str.strip(args["telegram_group_chat_id"])), args["telegram_topic_type"]
            ),
            axis=1,
        )

        return components.to_csv(index=False)

    @task
    def save_telegram_channels(mantaned_config: str, updated_config: str):
        mantened_components = pd.read_csv(StringIO(mantaned_config), dtype=str)
        updated_components = pd.read_csv(StringIO(updated_config), dtype=str)

        components = pd.concat([mantened_components, updated_components], axis=0, ignore_index=True)
        components.reset_index(drop=True)

        engine = _get_sql_engine(CONFIG_DB, SSH_CONN)
        components.loc[components["last_message_sent"].isnull(), "last_message_sent"] = (
            "2023-10-16 20:00:14.000 -0300"
        )
        components.to_sql(
            name="telegram_channels",
            con=engine,
            schema="telegram-moderation",
            if_exists="replace",
            index=False,
        )

    get_components_task = get_components()
    configure_topics_task = configure_topics(get_components_task["components_to_create_topics"])

    save_telegram_channels(get_components_task["components_to_maintain"], configure_topics_task)


create_telegram_moderation_config()

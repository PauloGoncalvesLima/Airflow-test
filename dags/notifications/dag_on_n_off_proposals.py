"""DAG to set proposals availability on decidim.

The result is the checkbox `Participantes podem criar propostas` marked as checked or not.

When setting decidim's proposals availability:
if permission_status is true
    then the code `marking` checkbox sends
        (component[step_settings][1][creation_enabled], 0)
        (component[step_settings][1][creation_enabled], 1)
else
    then the code `unmarking` checkbox sends
        (component[step_settings][1][creation_enabled], 0)

Permissions config

Comments Proposals | Permissions Config
    0       0      |    0
    0       1      |    1
    1       0      |    2
    1       1      |    3

"""

# pylint: disable=import-error, invalid-name, expression-not-assigned

import logging
import re
from collections import defaultdict
from datetime import timedelta

import bs4
from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.telegram.hooks.telegram import TelegramHook
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

from plugins.graphql.hooks.graphql_hook import GraphQLHook

import logging
from contextlib import closing
from os import walk
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Union
from urllib.parse import urljoin

import requests
from airflow.hooks.base import BaseHook
from airflow.models.connection import Connection

from plugins.utils.dict_utils import key_lookup

DECIDIM_CONN_ID = "api_decidim"
PAGE_FORM_CLASS = "form edit_component"



class GraphQLHook(BaseHook):
    """Uma classe para autenticação com uma API GraphQL usando o Apache Airflow.

    Esta classe, GraphQLHook, estende a classe BaseHook e fornece métodos para executar consultas GraphQL.

    Args:
    ----
        conn_id (str): O ID de conexão usado para autenticação.
        api_url (str): A URL base para a API GraphQL.
        auth_url (str): A URL para autenticação na API GraphQL.
        payload (dict): O payload contendo o email e a senha do usuário para autenticação.

    Methods:
    -------
        __init__(self, conn_id: str):
            Inicializa a instância GraphQLHook.

        get_graphql_query_from_file(self, path_para_arquivo_query: Union[Path, str]) -> str:
            Lê e retorna o conteúdo de um arquivo de consulta GraphQL.

        get_session(self) -> requests.Session:
            Cria uma sessão autenticada com as credenciais de usuário fornecidas.

        run_graphql_query(
            self, graphql_query: str, variables: Optional[Dict[str, Any]] = None
        ) -> Dict[str, str]:
            Executa uma consulta GraphQL e retorna a resposta em JSON.

        run_graphql_paginated_query(
            self,
            paginated_query: str,
            component_type: Optional[str] = None,
            variables: Optional[Dict[str, Any]] = None
        ) -> Generator[Dict[str, Any], None, None]:
            Executa uma consulta GraphQL paginada e gera respostas.

        get_components_ids_by_type(self, component_type: str):
            Obtém todos os IDs de componentes filtrados por tipo.
    """

    def __init__(self, conn_id: str):
        """
        Initializes the GraphQLHook instance.

        Args:
        ----
            conn_id (str): The connection ID used for authentication.
        """
        assert isinstance(conn_id, str), "Param type of conn_id has to be str"

        conn_values = self.get_connection(conn_id)
        assert isinstance(conn_values, Connection), "conn_values was not created correctly."

        self.conn_id = conn_id
        self.api_url = conn_values.host
        self.auth_url = urljoin(self.api_url, "api/sign_in")
        self.payload = {
            "user[email]": conn_values.login,
            "user[password]": conn_values.password,
        }

    def get_session(self) -> requests.Session:
        """
        Creates a requests session authenticated with the provided user credentials.

        Returns
        -------
            requests.Session: Authenticated session object.
        """
        session = requests.Session()

        try:
            r = session.post(self.auth_url, data=self.payload, verify=True)
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logging.info("A login error occurred: %s", e)
            raise e
        return session


def _convert_html_form_to_dict(html_form: bs4.element.Tag) -> defaultdict:
    """Convert html <form> and <input> tags to python dictionary.

    Args:
    ----
        html_form (bs4.element.Tag): beautiful soup object with
            respective html <form> filtered.

    Returns:
    -------
        defaultdict: a dictionary of lists with html input tag name
        and value.
    """
    dict_output = defaultdict(list)
    for tag in html_form.find_all("input"):
        if tag.get("type", None) == "checkbox":
            if tag.get("checked", None):
                dict_output[tag["name"]].append(tag["value"])
        else:
            dict_output[tag["name"]].append(tag["value"])

    return dict_output


def _find_form_input_id(dict_form: bs4.element.Tag, pattern: str):
    """Find a form input id using regex.

    Args:
    ----
        dict_form (bs4.element.Tag): a dict contains beautiful soup objects
            with respective html <form> filtered.

    Returns:
    -------
        form_input_id: a string with form input id value.

    Raises:
    ------
        IndexError: If does not found a component of creation enabled.
    """
    pattern_match = [component for component in dict_form if re.match(pattern, component)]
    logging.info(pattern_match)
    pattern_match = sorted(pattern_match)

    form_input_id = pattern_match.pop(0)

    logging.info("FORM_INPUT_ID: %s", form_input_id)

    return form_input_id


def set_comment_permmision(dict_form: dict, status: bool):
    comments_pattern = r"component\[.*step_settings\](\[[0-9]{1,}\]){0,1}\[comments_blocked\]"
    comments_form_input_id = _find_form_input_id(dict_form, comments_pattern)
    dict_form[comments_form_input_id] = [f"{int(not status)}"]


def set_proposals_permmision(dict_form: dict, status: bool):
    proposals_pattern = r"component\[.*step_settings\](\[[0-9]{1,}\]){0,1}\[creation_enabled\]"
    proposals_form_input_id = _find_form_input_id(dict_form, proposals_pattern)
    dict_form[proposals_form_input_id] = [f"{int(status)}"]


class DecidimNotifierDAGGenerator:  # noqa: D101
    def generate_dag(
        self,
        telegram_config: dict,
        component_id: str,
        process_id: str,
        start_date: str,
        end_date: str,
        decidim_url: str,
        permission_config: int,
        dag_id: str,
        schedule: str,
    ):
        self.component_id = component_id
        self.process_id = process_id
        self.permission_config = str(permission_config)

        self.telegram_conn_id = telegram_config["telegram_conn_id"]
        self.telegram_chat_id = telegram_config["telegram_group_id"]
        self.telegram_topic_id = telegram_config["telegram_moderation_proposals_topic_id"]

        self.most_recent_msg_time = f"most_recent_msg_time_{process_id}"
        self.start_date = start_date if isinstance(start_date, str) else start_date.strftime("%Y-%m-%d")
        if end_date is not None:
            self.end_date = end_date if isinstance(end_date, str) else end_date.strftime("%Y-%m-%d")
        else:
            self.end_date = end_date

        self.decidim_url = decidim_url

        default_args = {
            "owner": "Paulo G./Thais R.",
            "start_date": self.start_date,
            "end_date": self.end_date,
            "depends_on_past": False,
            "retries": 2,
            "retry_delay": timedelta(minutes=1),
            # "on_failure_callback": send_slack,
            # "on_retry_callback": send_slack, #! Change to telegram notifications.
        }

        @dag(
            dag_id=f"{dag_id}_{self.process_id}",
            default_args=default_args,
            schedule=schedule,
            catchup=False,
            description=__doc__,
            tags=["decidim"],
            is_paused_upon_creation=False,
        )
        def notify_on_n_off_permissions(
            permission_status: bool,
        ):  # pylint: disable=missing-function-docstring
            # due to Airflow DAG __doc__

            @task
            def set_permissions_availability(permission_status: bool):
                """Airflow task that makes a request to set status of `Participantes podem criar propostas`.

                It means that a decidim component became available or unavailable
                to receive new proposals.

                Args:
                ----
                    permission_status (bool): the desired action on the html
                        input checkbox `Participantes podem criar propostas`.
                """
                session = GraphQLHook(DECIDIM_CONN_ID).get_session()

                return_component_page = session.get(f"{self.decidim_url}")
                if return_component_page.status_code != 200:
                    raise HTTPError(f"Status code is {return_component_page.status_code} and not 200.")

                b = BeautifulSoup(return_component_page.text, "html.parser")
                html_form = b.find(class_=PAGE_FORM_CLASS)

                # logging.info(f"HTML Form:\n{html_form}")
                logging.info("Requesting page form from %s", self.decidim_url)

                dict_form = _convert_html_form_to_dict(html_form)

                # set permissions availability
                logging.info(self.permission_config)
                match self.permission_config:
                    case "1":
                        set_proposals_permmision(dict_form, permission_status)
                    case "2":
                        set_comment_permmision(dict_form, permission_status)
                    case "3":
                        set_proposals_permmision(dict_form, permission_status)
                        set_comment_permmision(dict_form, permission_status)

                data = list(dict_form.items())
                session.post(self.decidim_url.rstrip("/edit"), data=data)
                session.close()

            @task
            def send_telegram(permission_status: bool):
                """Airflow task to send telegram message.

                Args:
                ----
                    permission_status (bool): the desired action on the html
                        input checkbox `Participantes podem criar propostas`.
                """
                if permission_status:
                    message = "✅ <b>[ATIVADO]</b> \n\n<i>Participantes podem criar propostas e comentar</i>"
                else:
                    message = "🚫 <b>[DESATIVADO]</b> \n\n<i>Participantes não podem criar propostas nem comentar</i>"  # noqa: E501

                TelegramHook(
                    telegram_conn_id=self.telegram_conn_id,
                    chat_id=self.telegram_chat_id,
                ).send_message(
                    api_params={
                        "text": message,
                        "message_thread_id": self.telegram_topic_id,
                    }
                )

            set_permissions_availability(permission_status) >> send_telegram(permission_status)

        return notify_on_n_off_permissions


def yaml_to_dag(process_config: dict):
    """Recive the path to configuration file and generate an airflow dag."""
    DecidimNotifierDAGGenerator().generate_dag(
        **process_config,
        dag_id="notify_set_on_permissions",
        schedule="0 8 * * *",
    )(True)

    DecidimNotifierDAGGenerator().generate_dag(
        **process_config,
        dag_id="notify_set_off_permissions",
        schedule="0 22 * * *",
    )(False)


for config in eval(Variable.get("DAG_ON_OFF_CONFIG", [{}])):
    yaml_to_dag(config)

from datetime import datetime, timedelta  # noqa: I001
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from pathlib import Path
import smtplib

from airflow.decorators import dag, task
from airflow.hooks.base import BaseHook
import requests

from plugins.components.base_component.component import ComponentBaseHook
from plugins.graphql.hooks.graphql_hook import GraphQLHook
from plugins.reports.main import create_report_pdf

BP_CONN_ID = "bp_conn"


def _get_components_url(component_id: int):
    component_hook = ComponentBaseHook(BP_CONN_ID, component_id)
    return component_hook.get_component_link()


def _get_proposals_data(component_id: int, start_date: str, end_date: str):
    query = (
        Path(__file__)
        .parent.parent.parent.joinpath("./plugins/gql/reports/components/get_proposals_by_component_id.gql")
        .open()
        .read()
    )
    query_result = GraphQLHook(BP_CONN_ID).run_graphql_paginated_query(
        query, variables={"id": component_id, "start_date": start_date, "end_date": end_date}
    )

    result_proposals_data = []
    for page in query_result:
        component = page.get("data", {}).get("component", {})
        if not component:
            continue

        page_component_id = component.get("id")
        participatory_space_id = component.get("participatorySpace", {}).get("id")
        participatory_space_type = component.get("participatorySpace", {}).get("type", "").split("::")[-1]
        page_component_name = component.get("name", {}).get("translation", "-")
        page_proposals = component.get("proposals", {}).get("nodes", [])

        for proposal in page_proposals:
            proposal_id = proposal.get("id")
            proposal_title = proposal.get("title", {}).get("translation", "-")
            proposal_published_at = proposal.get("publishedAt")
            proposal_updated_at = proposal.get("updatedAt")
            proposal_state = proposal.get("state")
            proposal_total_comments = proposal.get("totalCommentsCount")
            proposal_total_votes = proposal.get("voteCount")
            proposal_category_title = (
                proposal.get("category", {}).get("name", {}).get("translation", "-")
                if proposal.get("category")
                else "-"
            )

            result_proposals_data.append(
                {
                    "page_component_id": page_component_id,
                    "participatory_space_id": participatory_space_id,
                    "participatory_space_type": participatory_space_type,
                    "page_component_name": page_component_name,
                    "proposal_id": proposal_id,
                    "proposal_title": proposal_title,
                    "proposal_published_at": proposal_published_at,
                    "proposal_updated_at": proposal_updated_at,
                    "proposal_state": proposal_state,
                    "proposal_total_comments": proposal_total_comments,
                    "proposal_total_votes": proposal_total_votes,
                    "proposal_category_title": proposal_category_title,
                }
            )
    return result_proposals_data


def _get_matomo_data(url: list, start_date: str, end_date: str, module: str, method: str):
    matomo_connection = BaseHook.get_connection("matomo_conn")
    matomo_url = matomo_connection.host
    token_auth = matomo_connection.password
    site_id = matomo_connection.login
    date_filter = f"{start_date},{end_date}"
    params = {
        "module": "API",
        "idSite": site_id,
        "period": "range",
        "date": date_filter,
        "segment": f"pageUrl=^{url}",
        "format": "csv",
        "token_auth": token_auth,
        "method": f"{module}.{method}",
    }
    logging.info("Params para a requisição do matomo \n%s.", params)

    response = requests.get(matomo_url, params=params)
    response.raise_for_status()

    try:
        return response.text
    except requests.exceptions.JSONDecodeError as error:
        logging.exception("Response text: %s", response.text)
        raise error


def _generate_report(bp_data, visits_summary, visits_frequency, user_country, devices_detection):
    pdf_bytes = create_report_pdf(bp_data, visits_summary, visits_frequency, user_country, devices_detection)

    return {"pdf_bytes": pdf_bytes}


def send_email_with_pdf(email: str, pdf_bytes: bytes, email_body: str, email_subject: str):
    smtp_server = "smtp_server"
    smtp_port = "port"
    smtp_user = "email"
    smtp_password = "password"

    message = MIMEMultipart()
    message["From"] = smtp_user
    message["To"] = email
    message["Subject"] = email_subject

    message.attach(MIMEText(email_body, "plain"))

    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename="report.pdf")
    message.attach(pdf_attachment)

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)

    print("E-mail enviado com sucesso!")


@dag(
    default_args={
        "owner": "Joyce/Paulo",
        "depends_on_past": False,
        "retries": 0,
        "retry_delay": timedelta(minutes=1),
    },
    schedule=None,
    catchup=False,
    start_date=datetime(2023, 11, 10),
    description=__doc__,
    tags=["decidim", "reports", "participacao", "bp"],
)
def generate_report_bp(email: str, start_date: str, end_date: str, component_id: int):
    """
    Gera um relatorio para o BP.

    1. Pegar todos os componentes do espaço participativo.
        1. Fazer a query para o BP com as datas passadas.
    2. Fazer a requisição para o matomo com as datas passadas.
    3. Gerar o relatorio.
    """

    @task
    def get_components_url(component_id: int):
        return _get_components_url(component_id)

    @task
    def get_component_data(component_id: int, filter_start_date: str, filter_end_date: str):
        return _get_proposals_data(component_id, filter_start_date, filter_end_date)

    get_components_url_task = get_components_url(component_id)

    def _get_matomo_extractor(url: str, matomo_module: str, matomo_method: str):
        @task(task_id=f"get_matomo_{matomo_module}_{matomo_method}")
        def matomo_extractor(
            url: str, filter_start_date: str, filter_end_date: str, module: str, method: str
        ):
            return _get_matomo_data(
                url=url, start_date=filter_start_date, end_date=filter_end_date, module=module, method=method
            )

        return matomo_extractor(
            url,
            start_date,
            end_date,
            matomo_module,
            matomo_method,
        )

    matomo_visits_summary_task = _get_matomo_extractor(get_components_url_task, "VisitsSummary", "get")
    matomo_visits_frequency_task = _get_matomo_extractor(get_components_url_task, "VisitFrequency", "get")
    matomo_user_contry_task = _get_matomo_extractor(get_components_url_task, "UserCountry", "getRegion")
    matomo_devices_detection_task = _get_matomo_extractor(
        get_components_url_task, "DevicesDetection", "getType"
    )

    @task(multiple_outputs=True)
    def generate_data(bp_data, visits_summary, visits_frequency, user_contry, devices_detection):
        return _generate_report(bp_data, visits_summary, visits_frequency, user_contry, devices_detection)

    @task
    def send_report_email(
        email: str, pdf_bytes: bytes, email_body: str, email_subject: str = "Seu Relatório"
    ):
        send_email_with_pdf(
            email=email,
            pdf_bytes=pdf_bytes,
            email_body=email_body,
            email_subject=email_subject,
        )

    get_components_data_task = get_component_data(
        component_id, filter_start_date=start_date, filter_end_date=end_date
    )

    generated_data = generate_data(
        get_components_data_task,
        visits_summary=matomo_visits_summary_task,
        visits_frequency=matomo_visits_frequency_task,
        user_contry=matomo_user_contry_task,
        devices_detection=matomo_devices_detection_task,
    )

    send_report_email(
        email=email,
        pdf_bytes=generated_data["pdf_bytes"],
        email_body="email_body",
        email_subject="email_subject",
    )

generate_report_bp("test@gmail.com", "2023-01-01", "2024-01-01", 2)

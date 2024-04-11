import io
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from airflow.decorators import dag, task, task_group
from airflow.operators.empty import EmptyOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.amazon.aws.operators.s3 import (
    S3CreateBucketOperator,
)
from airflow.providers.postgres.hooks.postgres import PostgresHook
from sqlalchemy.exc import ProgrammingError
from airflow.providers.amazon.aws.operators.s3 import S3CreateBucketOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
import pandas as pd
from io import StringIO
from plugins.graphql.hooks.graphql_hook import GraphQLHook
from typing import List, Tuple, Dict


default_args = {
    "owner": "Amoêdo",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retry_delay": timedelta(minutes=5),
}


def _add_temporal_columns(df: pd.DataFrame, execution_date: datetime) -> pd.DataFrame:
    """
    Adds temporal columns to the DataFrame based on the execution date.

    Args:
    ----
        df (pd.DataFrame): The original DataFrame without temporal columns.
        execution_date (datetime): The execution date to base the temporal columns on.

    Returns:
    -------
        pd.DataFrame: The DataFrame with added temporal columns.
    """
    event_day_id = int(execution_date.strftime("%Y%m%d"))
    available_day = execution_date + timedelta(days=1)
    available_day_id = int(available_day.strftime("%Y%m%d"))
    available_month_id = int(available_day.strftime("%Y%m"))
    available_year_id = int(available_day.strftime("%Y"))
    writing_day_id = int(datetime.now().strftime("%Y%m%d"))

    # Add the temporal columns to the DataFrame
    df["event_day_id"] = event_day_id
    df["available_day_id"] = available_day_id
    df["available_month_id"] = available_month_id
    df["available_year_id"] = available_year_id
    df["writing_day_id"] = writing_day_id

    return df

def _get_query(relative_path: str = "./queries/get_updat_at_proposals.gql"):
    """
    Retrieves the query from the specified file and returns it.

    Returns:
    -------
      str: The query string.
    """
    query = Path(__file__).parent.joinpath(relative_path).open().read()
    return query


def _extract_id_date_from_response(response: str) -> pd.DataFrame:
    """
    Extracts the id and date information from the given response.

    Args:
        response (str): The response string containing the data.

    Returns:
        pd.DataFrame: A DataFrame containing the extracted id and date information.
    """
    proposals_lists = []
    for process in response["data"]["participatoryProcesses"]:
        components = process.get("components")
        nodes_lists = [component.get("proposals", {}).get("nodes") or [] for component in components]

        for nodes in nodes_lists:
            proposals_lists.append(nodes)
    df_ids = pd.concat(pd.json_normalize(i) for i in proposals_lists)
    return df_ids


def _get_response_gql(query: str, response_text: bool = False, **variables):
    """
    Executes the GraphQL query to get the date and id of the update proposals.

    Parameters:
    ----------
    query : str
        The GraphQL query to be executed.

    Returns:
    -------
    dict
        The response from the GraphQL query.
    """
    hook = GraphQLHook(DECIDIM_CONN_ID)
    session = hook.get_session()
    response = session.post(
        hook.api_url,
        json={
            "query": query,
            "variables": variables,
        },
    )
    dado = response.text
    if response_text:
        return dado
    return json.loads(dado)


def _filter_ids_by_ds_nodash(ids: pd.DataFrame, date: str) -> pd.DataFrame:
    """
    Filter the given DataFrame based on the provided date.

    Args:
        ids (pd.DataFrame): The DataFrame containing the IDs and updated dates.
        date (str): The date to filter the DataFrame by.

    Returns:
        pd.DataFrame: The filtered DataFrame containing only the rows with the specified date.
    """
    print(ids.columns, "to aq")
    ids = ids[ids["updatedAt"].apply(lambda x: x[:10].replace("-", "")) == date]
    return list(ids["id"].values)


def collect_responses(ids: List[str], zone: str):
    s3 = S3Hook(MINIO_CONN)
    responses = []
    for _id in ids:
        response = s3.read_key(f"updated_proposals/{zone}/{_id}.json", MINIO_BUCKET)
        response = json.loads(response)
        responses.append(response)
    return responses



def dict_safe_get(_dict: dict, key: str):
    """
    Retorna o valor associado à chave especificada em um dicionário.

    Se a chave não existir ou o valor for None, retorna um dicionário vazio.

    Args:
    ----
      _dict (dict): O dicionário de onde obter o valor.
      key (str): A chave do valor desejado.

    Returns:
    -------
      O valor associado à chave especificada, ou um
      dicionário vazio se a chave não existir ou o valor for None.
    """
    value = _dict.get(key)
    if not value:
        value = {}
    return value



def flatten_structure_with_additional_fields(data, extract_by_id:bool = False):
    """
    Flattens the nested structure of the input data and.

    extracts additional fields for each proposal.

    Args:
    ----
      data (dict): The input data containing nested structure.

    Returns:
    -------
      list: A list of dictionaries, where each dictionary
      represents a flattened proposal with additional fields.

    """
    proposal_component = 'proposals'
    if extract_by_id:
        proposal_component = 'proposal'
    data = data["data"]["participatoryProcesses"]

    # Function to handle the extraction of text from nested translation dictionaries
    def extract_text(translations):
        if translations and isinstance(translations, list):
            return translations[0].get("text")


    flattened_data = []
    for item in data:
        main_title = extract_text(item.get("title", {}).get("translations", []))
        for component in item.get("components", []):
            component_id = component.get("id", "")
            component_name = extract_text(component.get("name", {}).get("translations", []))
            if proposal_component in component:
                if extract_by_id:
                    proposal = component.get(proposal_component)
                    if proposal:
                        proposal_data = get_proposal_dic(extract_text, main_title, component_id, component_name, proposal)
                        flattened_data.append(proposal_data)
                else:
                    for proposal in component.get("proposals", {}).get("nodes", []):
                        proposal_data = get_proposal_dic(extract_text, main_title, component_id, component_name, proposal)
                        flattened_data.append(proposal_data)
    return flattened_data



def get_proposal_dic(extract_text, main_title, component_id, component_name, proposal):
    proposal_data = {
                        "main_title": main_title,
                        "component_id": component_id,
                        "component_name": component_name,
                        "proposal_id": proposal["id"],
                        "proposal_created_at": proposal["createdAt"],
                        "proposal_published_at": proposal.get("publishedAt"),
                        "proposal_updated_at": proposal.get("updatedAt"),
                        "author_name": dict_safe_get(proposal, "author").get("name"),
                        "author_nickname": dict_safe_get(proposal, "author").get("nickname"),
                        "author_organization": dict_safe_get(proposal, "author").get("organizationName"),
                        "proposal_body": extract_text(proposal.get("body", {}).get("translations", [])),
                        "category_name": extract_text(
                            dict_safe_get(dict_safe_get(proposal, "category"), "name").get("translations", [])
                        ),
                        "proposal_title": extract_text(proposal.get("title", {}).get("translations", [])),
                        "authors_count": proposal.get("authorsCount"),
                        "user_allowed_to_comment": proposal.get("userAllowedToComment"),
                        "endorsements_count": proposal.get("endorsementsCount"),
                        "total_comments_count": proposal.get("totalCommentsCount"),
                        "versions_count": proposal.get("versionsCount"),
                        "vote_count": proposal.get("voteCount"),
                        "comments_have_alignment": proposal.get("commentsHaveAlignment"),
                        "comments_have_votes": proposal.get("commentsHaveVotes"),
                        "created_in_meeting": proposal.get("createdInMeeting"),
                        "has_comments": proposal.get("hasComments"),
                        "official": proposal.get("official"),
                        "fingerprint": proposal.get("fingerprint", {}).get("value"),
                        "position": proposal.get("position"),
                        "reference": proposal.get("reference"),
                        "scope": proposal.get("scope"),
                        "state": proposal.get("state"),
                    }
    
    return proposal_data


def _convert_to_csv(proposal:dict) -> StringIO:
    """
    Converts a proposal to a CSV format.

    Args:
        proposal (pd.DataFrame): The proposal data to be converted.

    Returns:
        StringIO: A buffer containing the CSV data.
    """
    proposal = pd.DataFrame(proposal)
    proposal = _add_temporal_columns(proposal, datetime.now())
    csv_buffer = StringIO()
    proposal.to_csv(csv_buffer, index=False)
    return csv_buffer


QUERY = _get_query()
DECIDIM_CONN_ID = "api_decidim"
MINIO_CONN = "minio_conn_id"
MINIO_BUCKET = "brasil-participativo-daily-csv"
LANDING_ZONE = "landing_zone"
PROCESSING_ZONE = "processing"
PROCESSED_ZONE = "processed"


@dag(
    default_args=default_args,
    schedule_interval="0 22 * * *",
    start_date=datetime(2021, 1, 1),
    catchup=False,
    tags=["data_lake"],
)
def ingest_update_proposals():
    start = EmptyOperator(task_id="start")

    @task
    def get_date_id_update_proposals():
        query = _get_query()
        response = _get_response_gql(query)
        response = _extract_id_date_from_response(response)
        return response

    @task(provide_context=True)
    def get_current_updated_ids(ids: pd.DataFrame, **context):
        ids = _filter_ids_by_ds_nodash(ids, context["ds_nodash"])
        return ids

    check_and_create_bucket = S3CreateBucketOperator(
        task_id="check_and_create_bucket",
        bucket_name=MINIO_BUCKET,
        aws_conn_id=MINIO_CONN,
    )

    @task
    def get_updated_proposals(ids: List[str]):
        query = _get_query("./queries/get_proposals_by_id.gql")
        print(query)
        for _id in ids:
            response = _get_response_gql(query, response_text=True, id=_id)
            print(response)
            hook = S3Hook(MINIO_CONN)
            hook.load_string(
                response,
                key=f"updated_proposals/landing_zone/{_id}.json",
                bucket_name=MINIO_BUCKET,
                replace=True,
            )

    @task(provide_context=True)
    def transform_updated_proposals(**context):
        ids = context["task_instance"].xcom_pull(task_ids="get_current_updated_ids")
        responses = collect_responses(ids, LANDING_ZONE)
        for response, _id in zip(responses, ids):
            proposal:dict = flatten_structure_with_additional_fields(response, extract_by_id=True)
            csv_buffer = _convert_to_csv(proposal)
            hook = S3Hook(MINIO_CONN) 
            hook.load_string(
            string_data=csv_buffer.getvalue(),
            bucket_name=MINIO_BUCKET,
            key=f'updated_proposals/{PROCESSING_ZONE}/{_id}.csv',
            replace=True,
        )


    check_and_create_schema = PostgresOperator(
        task_id="check_and_create_schema",
        sql="CREATE SCHEMA IF NOT EXISTS decidim;",
        postgres_conn_id="conn_postgres",
    )
    
    @task(provide_context=True)
    def insert_updeted_proposals(**context):
        ids = context["task_instance"].xcom_pull(task_ids="get_current_updated_ids")
        responses = collect_responses(ids, PROCESSING_ZONE)
        print(responses)
        

    _get_date_id_update_proposals = get_date_id_update_proposals()
    start >> _get_date_id_update_proposals
    _get_current_updated_ids = get_current_updated_ids(_get_date_id_update_proposals)
    _get_updated_proposals = get_updated_proposals(_get_current_updated_ids)
    _get_current_updated_ids >> check_and_create_bucket >> _get_updated_proposals
    _get_updated_proposals >> transform_updated_proposals() >> check_and_create_schema
    check_and_create_schema >> insert_updeted_proposals()

dag = ingest_update_proposals()





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
TABLE_PROPOSALS = 'decidim_proposals_proposals'
TABLE_PARTICIPATORY_PROCESSES = "decidim_participatory_processes"
VARIABLE = 'registry_numbers'

def get_postgres_connection():
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN)
    connection = hook.get_conn()
    return connection

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
        postgres_cursor = get_postgres_connection().cursor()

        last_operation_count  = Variable.get(VARIABLE, default_var=0)

        logging.info(f"O último elemento da operação anterior é: {last_operation_count}")

        query = f"""
            SELECT *
            FROM {SCHEMA}.{TABLE_PROPOSALS}
            WHERE id > {last_operation_count}
            ORDER BY id ASC;
        """

        postgres_cursor.execute(query)
        result = postgres_cursor.fetchall()

        if result:
            last_id_query = result[-1][0]
            logging.info(f"Query executada no banco, o último elemento atualmente é: {last_id_query}")
            
            if last_id_query > last_operation_count:
                # Variable.set(VARIABLE, last_id_query)
                return result


    @task
    def transform_data(ti=None):
        if ti.xcom_pull(task_ids='verify_atualization') is None:
            logging.info(f"Não há novas atualizações!")
            return
        
        data = ti.xcom_pull(task_ids='verify_atualization')

        cursor_postgres = get_postgres_connection(). cursor()

        components_proposals = {components[1] for components in data}


        query = f"""
            SELECT dc.id, dc.participatory_space_id, dpp.id AS participatory_process_id, dpp.decidim_participatory_process_group_id
            FROM decidim_components dc
            JOIN decidim_participatory_processes dpp
            ON dc.participatory_space_id = dpp.id
            WHERE dc.id IN ({','.join(map(str, components_proposals))});
        """
        
        cursor_postgres.execute(query)
        participatory_processes = cursor_postgres.fetchall()

        logging.info(f"Paticipatory processes id and groups added!\n")

        processes_dict = {comp[0]: {
            "participatory_process_id": comp[2],
            "participatory_process_group_id": comp[3]
        } for comp in participatory_processes}

        logging.info(f"Paticipatory processes id added!\n")
        
        cursor_postgres.execute(query)
        participatory_processes = cursor_postgres.fetchall()

        data_json = { }

        json_list = []
        for values_data in data:
            component_id = values_data[1]
            if component_id in processes_dict:
                participatory_data = processes_dict[component_id]
                data_json = {
                    "id": values_data[0],
                    "decidim_component_id": component_id,
                    "decidim_participatory_processes": participatory_data["participatory_process_id"],
                    "decidim_participatory_process_group_id": participatory_data["participatory_process_group_id"],
                    "decidim_scope_id": values_data[2],
                    "created_at": values_data[3].strftime("%d/%m/%Y %H:%M:%S"),
                    "updated_at": values_data[4],
                    "proposal_votes_count": values_data[5],
                    "state": values_data[6],
                    "answered_at": values_data[7],
                    "answer": values_data[8],
                    "reference": values_data[9],
                    "address": values_data[10],
                    "latitude": values_data[11],
                    "longitude": values_data[12],
                    "published_at": values_data[13].strftime("%d/%m/%Y %H:%M:%S"),
                    "proposal_notes_count": values_data[14],
                    "coauthorships_count": values_data[15],
                    "participatory_text_level": values_data[16],
                    "position": values_data[17],
                    "created_in_meeting": values_data[18],
                    "cost": values_data[19],
                    "cost_report": values_data[20],
                    "execution_period": values_data[21],
                    "state_published_at": values_data[22],
                    "endorsements_count": values_data[23],
                    "title": values_data[24],
                    "body": values_data[25],
                    "comments_count": values_data[26],
                    "follows_count": values_data[27],
                    "is_interactive": values_data[28],
                    "badge_array": values_data[29] 
                }
                json_list.append(data_json)
                logging.info(f"JSON: {data_json}")

        logging.info(f"JSON gerado com sucesso: {json_list}")
        return json_list


    @task(task_id='sending_messages')
    def sending_messages(ti=None):

        json_data = ti.xcom_pull(task_ids='transform_data')

        logging.info(f"JSON gerado com sucesso: {json_data}")

        state_map = {
        "accepted": {"label": "aceita ", "emoji": "✅ ✅ ✅"},
        "evaluating": {"label": "em avaliação ", "emoji": "📥 📥 📥"},
        "withdrawn": {"label": "retirada ", "emoji": "🚫 🚫 🚫"},
        "rejected": {"label": "rejeitada ", "emoji": "⛔️ ⛔️ ⛔️"},
        "others": {"label": "atualizada ", "emoji": "🔄 🔄 🔄"},
        "new": {"label": "", "emoji": "📣 📣 📣 <b>[NOVA]</b>"},
        }

        message =[]

        for value in json_data:
            for label, characteristics in state_map.items():
                if label in value['state']:
                    message.append(f"{characteristics['emoji']} Proposta <b>{characteristics['label']}</b>em {value['published_at']}\n\n")
                    f"<b>Proposta</b>\n{value['title']}\n\n"
                    f"<b>Autor</b>\n{value['aut']} {organization_name}\n\n"
                    f"<b>Categoria</b>\n{data_row['category']}\n\n"
                    f"<b>Descrição</b>\n{value['body']}\n\n")

        logging.info(f"Imprimindo vetor de mensagens: {message}")

        telegram_hook = TelegramHook(telegram_conn_id=TELEGRAM_CONN_ID)

        # telegram_hook.send_message(
        #     {
        #         'chat_id': '',  # Chat ID do grupo ou canal
        #         'text': 'This is a test message from Airflow!'
        #     }
        # )



    start >> verify_atualization_db() >> transform_data() >> sending_messages() >> end

automation_notify_telegram()
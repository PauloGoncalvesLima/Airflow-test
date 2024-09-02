import argparse
import json
from contextlib import closing
from pathlib import Path

doc_md_DAG = '''

## Documentação da DAG `data_ingestion_postgres_cursor_ingestion`

### Descrição

A DAG `data_ingestion_postgres_cursor_ingestion` é responsável pela extração de dados de várias tabelas em um banco de dados PostgreSQL, utilizando uma configuração específica para cada tabela armazenada em arquivos `.json`. Esta DAG realiza tanto ingestações completas quanto incrementais e armazena os dados extraídos em um banco de dados de destino especificado.

### Detalhes da DAG

- **ID da DAG**: `data_ingestion_postgres_cursor_ingestion`
- **Tags**: `ingestion`, `{nome_da_tabela}` (as tags incluem a identificação de cada tabela conforme configurada no arquivo JSON)
- **Proprietário**: `data`
- **Agendamento**: Diariamente às 04:00 UTC (`0 4 * * *`)
- **Data de início**: Configurada conforme especificado no arquivo JSON de cada tabela.
- **Catchup**: Configurado conforme especificado no arquivo JSON de cada tabela.
- **Concurrency**: 1 (apenas uma execução da DAG por vez)
- **Renderização de templates como objetos nativos**: Ativado (`True`)

### Argumentos Padrão

- **Retries**: 2 (número de tentativas em caso de falha)
- **Retry Delay**: 10 minutos (tempo de espera entre as tentativas)

### Configuração da Ingestão

Esta DAG processa múltiplas tabelas conforme descrito em arquivos `.json` localizados no diretório `./cursor_ingestions`. Cada arquivo JSON deve conter as seguintes informações:

- **name**: Nome da extração (utilizado na definição da DAG e nas tarefas).
- **extractions**: Dicionário contendo as extrações a serem realizadas, onde cada chave representa o nome de uma tabela e o valor é um dicionário com as seguintes informações:
  - `extraction_schema`: Esquema de origem da tabela.
  - `ingestion_type`: Tipo de ingestão (`full_refresh` ou `incremental`).
  - `incremental_filter`: Filtro utilizado para identificar os novos dados em ingestações incrementais.
  - `destination_schema`: Esquema de destino onde os dados serão armazenados.
- **catchup**: Define se a DAG deve realizar catchup.
- **start_date**: Data de início da DAG no formato `YYYY-MM-DD`.
- **origin_db_connection**: ID da conexão para o banco de dados de origem no Airflow.
- **destination_db_connection**: ID da conexão para o banco de dados de destino no Airflow.

### Estrutura da DAG

Para cada extração configurada, a DAG cria duas tarefas:

#### 1. `extract_data_{nome_da_tabela}`

**Operador**: `PythonVirtualenvOperator`

- **Descrição**: Extrai os dados de uma tabela específica do banco de dados de origem utilizando o tipo de ingestão especificado (com ou sem túnel SSH).
- **Parâmetros de Entrada**:
  - `extraction`: Nome da tabela a ser extraída.
  - `extraction_info`: Informações de configuração da extração, conforme descritas no arquivo JSON.
  - `db_conn_id`: ID da conexão do banco de dados de origem no Airflow.
  - `ssh_tunnel`: Indica se deve ser utilizado um túnel SSH (padrão `True`).
- **Bibliotecas Necessárias**: `pandas`, `sqlalchemy`, `sshtunnel`
- **Saída**: Retorna um DataFrame contendo os dados extraídos.

#### 2. `write_data_{nome_da_tabela}`

**Operador**: `PythonVirtualenvOperator`

- **Descrição**: Escreve os dados extraídos na tabela de destino especificada no banco de dados de destino.
- **Parâmetros de Entrada**:
  - `df`: DataFrame contendo os dados extraídos.
  - `extraction`: Nome da tabela a ser escrita.
  - `extraction_info`: Informações de configuração da extração, conforme descritas no arquivo JSON.
  - `db_conn_id`: ID da conexão do banco de dados de destino no Airflow.
- **Bibliotecas Necessárias**: `pandas`, `sqlalchemy`
- **Saída**: Escreve os dados no banco de dados de destino, no esquema e tabela especificados.

#### Conexões e Relacionamentos

- Cada par de tarefas (`extract_data_{nome_da_tabela}` e `write_data_{nome_da_tabela}`) está encadeado, ou seja, a tarefa de extração deve ser concluída com sucesso antes que a tarefa de escrita seja executada.

### Conexões com Datasets

- **Output Dataset**: Cada tabela extraída gera um `Dataset` correspondente, identificado pelo nome `bronze_{nome_da_tabela}`.
'''


def parse_args():
    parser = argparse.ArgumentParser(description="Process dbt manifest and generate Airflow DAG.")
    parser.add_argument(
        "--manifest_path",
        default="dbt_pg_project/target/manifest.json",
        required=False,
        help="Path to the dbt manifest file",
    )
    parser.add_argument(
        "--project_path", default="dbt_pg_project", required=False, help="Path to the dbt project"
    )
    parser.add_argument(
        "--profile_path", default="dbt_pg_project", required=False, help="Path to the dbt profile"
    )
    parser.add_argument(
        "--dag_folder_path",
        default="dags/dbt/",
        required=False,
        help="Folder path where generated DAGs will be saved",
    )
    return parser.parse_args()


def get_manifest(manifest_path):
    with open(manifest_path) as f:
        manifest = json.load(f)
    return manifest


def generate_airflow_task(node_type, node_name, dbt_project_path, dbt_profile_path, indentation="    "):
    type2command = {"model": "run", "test": "test"}
    dbt_command = type2command[node_type]
    task_id = f"{dbt_command}_{node_name}"
    k8s_dbt_project_path = f"/tmp/dbt_{dbt_command}_{node_name}"
    task = f"""
{indentation}{node_name}_task = BashOperator(
{indentation}{indentation}task_id='{task_id}',
{indentation}{indentation}bash_command='rm -r {k8s_dbt_project_path} || true \\
&& cp -r {dbt_project_path} {k8s_dbt_project_path} \\
&& cd {k8s_dbt_project_path} \\
&& dbt deps && dbt {dbt_command} --select {node_name} \\
&& rm -r {k8s_dbt_project_path}',
{indentation}{indentation}env={{
{indentation}{indentation}{indentation}'DBT_POSTGRES_HOST': Variable.get("bp_dw_pg_host"),
{indentation}{indentation}{indentation}'DBT_POSTGRES_USER': Variable.get("bp_dw_pg_user"),
{indentation}{indentation}{indentation}'DBT_POSTGRES_PASSWORD': Variable.get("bp_dw_pg_password"),
{indentation}{indentation}{indentation}'DBT_POSTGRES_ENVIRONMENT': Variable.get("bp_dw_pg_environment"),
{indentation}{indentation}{indentation}'DBT_POSTGRES_PORT': Variable.get("bp_dw_pg_port"),
{indentation}{indentation}{indentation}'DBT_POSTGRES_DATABASE': Variable.get("bp_dw_pg_db"),
{indentation}{indentation}}},
{indentation}{indentation}append_env=True
{indentation})"""
    return task


def generate_airflow_schedule(model_dependencies, nodes_type_map):
    if not model_dependencies:
        return "'@daily'"

    model_dependencies = [
        f"{model}_model" if model in nodes_type_map else f"{model}" for model in model_dependencies
    ]

    schedule_dataset = ", ".join([f"Dataset('{dep}')" for dep in model_dependencies])
    return f"[{schedule_dataset}]"


def generate_airflow_dag_id(node, nodes_type_map):
    return f"run_{nodes_type_map[node]}__{node}"


def create_dependencies(node, model_tests_dependencies: list, indentation="    "):
    if not model_tests_dependencies:
        return [f"{indentation}{node}_task >> end_task"]

    dependencies = []
    for test_dependecy in model_tests_dependencies:
        dependencies.append(f"{indentation}{node}_task >> {test_dependecy}_task >> end_task")
    return dependencies


def parse_manifest(manifest):
    nodes = manifest["nodes"]
    nodes_type_map = {node["name"]: node["resource_type"] for _, node in nodes.items()}

    datasets_map = {}
    for _, node in nodes.items():
        if "datasets_trigger" in node["meta"]:
            triggers = node["meta"]["datasets_trigger"]
            if isinstance(triggers, str):
                triggers = triggers.split(",")
            assert isinstance(triggers, list)
            datasets_map[node["name"]] = triggers

    upstreams = {}
    for _, node in nodes.items():
        node_name = node["name"]
        depends_on = node["depends_on"]
        node_dependencies = depends_on.get("nodes", [])
        node_dependencies = [nodes[dep]["name"] for dep in node_dependencies if dep.startswith("model")]
        upstreams[node_name] = node_dependencies
    return upstreams, nodes_type_map, datasets_map


def get_models_dependecies(upstreams, nodes_type_map, datasets_map):
    tests_dependecies = {}
    for node, upstream in upstreams.items():
        if nodes_type_map[node] != "test":
            continue
        for dep in upstream:
            _map = tests_dependecies.get(dep, [])
            _map.append(node)
            tests_dependecies[dep] = _map

    models_dependecies = {
        node: [*deps, *datasets_map.get(node, [])]
        for node, deps in upstreams.items()
        if nodes_type_map[node] == "model"
    }

    dependencies = {
        node: {
            "tests_dependecies": tests_dependecies.get(node, []),
            "model_dependecies": models_dependecies[node],
        }
        for node in models_dependecies
    }

    return dependencies


def generate_airflow_dags(dag_folder_path, manifest, dbt_project_path, dbt_profile_path):
    upstreams, nodes_type_map, datasets_map = parse_manifest(manifest)
    models_dependecies = get_models_dependecies(upstreams, nodes_type_map, datasets_map)

    dag_path = Path(dag_folder_path)
    if not dag_path.exists():
        dag_path.mkdir(parents=True, exist_ok=True)

    for node, dependencies in models_dependecies.items():
        tasks_str = "\n".join(
            [
                generate_airflow_task(nodes_type_map[dbt_node], dbt_node, dbt_project_path, dbt_profile_path)
                for dbt_node in [node, *dependencies["tests_dependecies"]]
            ]
        )
        tests_dependencies = create_dependencies(node, dependencies["tests_dependecies"], indentation="    ")
        dependencies_str = "\n".join(tests_dependencies) if tests_dependencies else ""

        dag_name = generate_airflow_dag_id(node, nodes_type_map)

        with closing(open(Path(__file__).parent.joinpath("./dag_template.txt"))) as dag_template_file:
            dag_content = dag_template_file.read()
        assert dag_content is not None

        with open(dag_path.joinpath(f"{dag_name}.py"), "w") as f:
            f.write(
                dag_content.format(
                    dag_id=dag_name,
                    tasks_str=tasks_str,
                    node_type=nodes_type_map[node],
                    dependencies_str=dependencies_str,
                    dag_trigger=generate_airflow_schedule(dependencies["model_dependecies"], nodes_type_map),
                    outlet_dataset=f"{node}_model",
                    doc_md=doc_md_DAG
                )
            )


if __name__ == "__main__":
    args = parse_args()
    manifest = get_manifest(args.manifest_path)
    generate_airflow_dags(args.dag_folder_path, manifest, args.project_path, args.profile_path)

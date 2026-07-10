import sys
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# dbt lives in its own venv inside the image (see Dockerfile) -- its
# dependencies conflict with Airflow's own constraints file, so it can't
# share Airflow's Python environment.
DBT_BIN = "/home/airflow/dbt-venv/bin/dbt"
DBT_PROJECT_DIR = "/opt/airflow/dbt"

sys.path.insert(0, "/opt/airflow/scripts")


def load_raw():
    from load_raw import load_raw_table

    load_raw_table("whoscored_events")
    load_raw_table("whoscored_matches")


with DAG(
    dag_id="events_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule=None,  # manual trigger: gated on a human WhoScored export, not a fixed cadence
    catchup=False,
) as dag:
    load_raw_task = PythonOperator(
        task_id="load_raw",
        python_callable=load_raw,
    )

    run_staging = BashOperator(
        task_id="run_staging",
        bash_command=(
            f"{DBT_BIN} run --select staging "
            f"--project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"
        ),
    )

    run_marts = BashOperator(
        task_id="run_marts",
        bash_command=(
            f"{DBT_BIN} run --select marts "
            f"--project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"
        ),
    )

    load_raw_task >> run_staging >> run_marts

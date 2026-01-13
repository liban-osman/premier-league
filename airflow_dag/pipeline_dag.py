from airflow import DAG
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from datetime import datetime

with DAG(
    dag_id="prem_pipeline",
    start_date=datetime(2024,1,1),
    schedule_interval="@daily",
    catchup=False
) as dag:

    load_raw = SnowflakeOperator(
        task_id="load_raw",
        snowflake_conn_id="snowflake_prem",
        sql="sql/raw/load_raw.sql"
    )

    transform_silver = SnowflakeOperator(
        task_id="transform_silver",
        snowflake_conn_id="snowflake_prem",
        sql="sql/silver/transform_events_silver.sql"
    )

    aggregate_gold = SnowflakeOperator(
        task_id="aggregate_gold",
        snowflake_conn_id="snowflake_prem",
        sql="sql/gold/aggregate_pass_maps.sql"
    )

    load_raw >> transform_silver >> aggregate_gold

FROM apache/airflow:2.10.5-python3.11

ARG AIRFLOW_VERSION=2.10.5
ARG PYTHON_VERSION=3.11

USER airflow

# duckdb has almost no dependencies of its own, so unlike dbt it installs
# cleanly straight into Airflow's environment. Used by the load_raw task
# (scripts/load_raw.py) via PythonOperator.
RUN pip install --no-cache-dir \
    "duckdb" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# dbt-core's dependency tree (via dbt-semantic-interfaces) conflicts with
# Airflow's own pinned versions (e.g. isodate) even against Airflow's
# constraints file. Rather than fight that resolution, dbt gets its own
# isolated venv so it never shares site-packages with Airflow at all.
RUN python -m venv /home/airflow/dbt-venv && \
    /home/airflow/dbt-venv/bin/pip install --no-cache-dir dbt-core dbt-duckdb

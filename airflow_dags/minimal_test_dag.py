from datetime import datetime
from airflow.decorators import dag
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'data-engineering-team'
}

@dag(
    dag_id='minimal_test_dag',
    start_date=datetime(2024, 1, 1),  # Past date
    schedule=None,
    catchup=False,
    default_args=default_args,
    tags=['test'],
)
def minimal_test_dag():
    """A simple test DAG to verify the MWAA environment is working."""
    BashOperator(
        task_id='hello_world',
        bash_command='echo "Minimal test DAG is working!"',
    )

minimal_test_dag()
import pendulum
from airflow.decorators import dag
from airflow.operators.bash import BashOperator

@dag(
    dag_id='minimal_test_dag',
    start_date=pendulum.datetime(2025, 7, 17, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=['test'],
)
def minimal_test_dag():
    """A simple test DAG to verify the MWAA environment is working."""
    BashOperator(
        task_id='hello_world',
        bash_command='echo "Minimal test DAG is working!"',
    )

minimal_test_dag()
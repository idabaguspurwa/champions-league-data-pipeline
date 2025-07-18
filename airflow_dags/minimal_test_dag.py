import pendulum
from airflow.decorators import dag
from airflow.operators.bash import BashOperator

# Define default arguments, including a specific owner.
default_args = {
    'owner': 'data-engineering-team'
}

@dag(
    dag_id='minimal_test_dag',
    start_date=pendulum.datetime(2025, 7, 18, tz="Asia/Jakarta"),
    schedule=None,
    catchup=False,
    default_args=default_args, # Apply the default args to the DAG
    tags=['test'],
)
def minimal_test_dag():
    """A simple test DAG to verify the MWAA environment is working."""
    BashOperator(
        task_id='hello_world',
        bash_command='echo "Minimal test DAG is working!"',
    )

minimal_test_dag()
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator

def test_function():
    print("Test DAG is working!")
    return "Success"

default_args = {
    'owner': 'data-engineering-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'minimal_test_dag',
    default_args=default_args,
    description='A minimal test DAG',
    schedule_interval=None,
    catchup=False,
    tags=['test']
)

# Use BashOperator instead of decorators
hello_world = BashOperator(
    task_id='hello_world',
    bash_command='echo "Minimal test DAG is working!"',
    dag=dag
)

# Add a Python task
python_task = PythonOperator(
    task_id='python_task',
    python_callable=test_function,
    dag=dag
)

hello_world >> python_task
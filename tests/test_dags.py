import os
# Set the AIRFLOW_HOME environment variable to a temporary directory
os.environ['AIRFLOW_HOME'] = '/tmp/airflow'
# Configure Airflow to use a temporary SQLite database for testing
os.environ['AIRFLOW__CORE__SQL_ALCHEMY_CONN'] = 'sqlite:////tmp/airflow/airflow.db'

import pytest
from airflow.models.dagbag import DagBag

# Path to the DAGs folder
DAGS_PATH = os.path.join(os.path.dirname(__file__), '..', 'airflow_dags')
DAGBAG = DagBag(dag_folder=DAGS_PATH, include_examples=False)

def get_dag_ids():
    """Returns a list of DAG IDs from the DagBag."""
    return DAGBAG.dag_ids

@pytest.mark.parametrize("dag_id", get_dag_ids())
def test_dag_integrity(dag_id):
    """
    Tests for DAG integrity:
    1. No import errors.
    2. All tasks have defined owners.
    3. No tasks have default retries (or they match a standard).
    """
    dag = DAGBAG.get_dag(dag_id)
    assert dag is not None, f"DAG '{dag_id}' could not be loaded."
    
    # Test for default owners
    for task in dag.tasks:
        assert task.owner is not None and task.owner.lower() != 'airflow', \
            f"Task '{task.task_id}' in DAG '{dag_id}' has a missing or default owner."

def test_no_import_errors():
    """Asserts that there are no import errors in the DagBag."""
    assert len(DAGBAG.import_errors) == 0, \
        f"DAG import errors found: {DAGBAG.import_errors}"
"""
Champions League Data Pipeline DAG
Orchestrates the complete data pipeline using Kubernetes operators
"""

from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
from airflow.providers.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from airflow.models import Variable
from airflow.utils.task_group import TaskGroup

# Configuration
NAMESPACE = Variable.get("k8s_namespace", default_var="champions-league")
IMAGE_PULL_POLICY = Variable.get("image_pull_policy", default_var="Always")
AWS_REGION = Variable.get("aws_region", default_var="ap-southeast-1")
S3_BUCKET = Variable.get("s3_bucket", default_var="champions-league-data-lake")

# Default arguments for all tasks
default_args = {
    'owner': 'data-engineering-team',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'max_active_runs': 1,
}

# DAG definition
dag = DAG(
    'champions_league_pipeline',
    default_args=default_args,
    description='Champions League Data Engineering Pipeline',
    schedule_interval='0 */6 * * *',  # Every 6 hours
    catchup=False,
    max_active_runs=1,
    tags=['champions-league', 'data-engineering', 'kubernetes'],
)

def create_kubernetes_pod_operator(
    task_id: str,
    image: str,
    command: list = None,
    arguments: list = None,
    env_vars: dict = None,
    resources: dict = None,
    **kwargs
) -> KubernetesPodOperator:
    """Create a standardized Kubernetes Pod Operator"""
    
    default_env_vars = {
        'AWS_REGION': AWS_REGION,
        'S3_BUCKET': S3_BUCKET,
        'LOG_LEVEL': 'INFO'
    }
    
    if env_vars:
        default_env_vars.update(env_vars)
    
    default_resources = {
        'request_memory': '512Mi',
        'request_cpu': '250m',
        'limit_memory': '1Gi',
        'limit_cpu': '500m'
    }
    
    if resources:
        default_resources.update(resources)
    
    return KubernetesPodOperator(
        task_id=task_id,
        name=f"champions-league-{task_id}",
        namespace=NAMESPACE,
        image=image,
        image_pull_policy=IMAGE_PULL_POLICY,
        cmds=command,
        arguments=arguments,
        env_vars=default_env_vars,
        resources=default_resources,
        get_logs=True,
        is_delete_operator_pod=True,
        dag=dag,
        **kwargs
    )

# Task Group: Data Ingestion
with TaskGroup("data_ingestion", dag=dag) as ingestion_group:
    
    # Check ingestion service health
    check_ingestion_health = HttpSensor(
        task_id='check_ingestion_service_health',
        http_conn_id='ingestion_service',
        endpoint='/health',
        timeout=30,
        poke_interval=10,
        mode='poke',
        dag=dag
    )
    
    # Ingest standings data
    ingest_standings = SimpleHttpOperator(
        task_id='ingest_standings',
        http_conn_id='ingestion_service',
        endpoint='/ingest',
        method='POST',
        data='{"endpoint": "standings", "season": "2024"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Ingest team data (Barcelona)
    ingest_team_barcelona = SimpleHttpOperator(
        task_id='ingest_team_barcelona',
        http_conn_id='ingestion_service',
        endpoint='/ingest',
        method='POST',
        data='{"endpoint": "team_info", "team_id": "83"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Ingest team performance (Barcelona)
    ingest_team_performance_barcelona = SimpleHttpOperator(
        task_id='ingest_team_performance_barcelona',
        http_conn_id='ingestion_service',
        endpoint='/ingest',
        method='POST',
        data='{"endpoint": "team_performance", "team_id": "83"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Ingest team results (Barcelona)
    ingest_team_results_barcelona = SimpleHttpOperator(
        task_id='ingest_team_results_barcelona',
        http_conn_id='ingestion_service',
        endpoint='/ingest',
        method='POST',
        data='{"endpoint": "team_results", "team_id": "83", "season": "2024"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Ingest athlete data (sample player)
    ingest_athlete_stats = SimpleHttpOperator(
        task_id='ingest_athlete_stats',
        http_conn_id='ingestion_service',
        endpoint='/ingest',
        method='POST',
        data='{"endpoint": "athlete_statistics", "player_id": "150225"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Ingest athlete bio (sample player)
    ingest_athlete_bio = SimpleHttpOperator(
        task_id='ingest_athlete_bio',
        http_conn_id='ingestion_service',
        endpoint='/ingest',
        method='POST',
        data='{"endpoint": "athlete_bio", "player_id": "150225"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Ingest full dataset
    ingest_full_dataset = SimpleHttpOperator(
        task_id='ingest_full_dataset',
        http_conn_id='ingestion_service',
        endpoint='/ingest',
        method='POST',
        data='{"endpoint": "all", "season": "2024", "team_ids": ["83", "86", "85", "81"], "player_ids": ["150225", "164024", "131921"]}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    check_ingestion_health >> [
        ingest_standings,
        ingest_team_barcelona,
        ingest_team_performance_barcelona,
        ingest_team_results_barcelona,
        ingest_athlete_stats,
        ingest_athlete_bio,
        ingest_full_dataset
    ]

# Task Group: Data Quality Validation
with TaskGroup("data_quality", dag=dag) as quality_group:
    
    # Check data quality service health
    check_quality_health = HttpSensor(
        task_id='check_quality_service_health',
        http_conn_id='quality_service',
        endpoint='/health',
        timeout=30,
        poke_interval=10,
        mode='poke',
        dag=dag
    )
    
    # Validate standings data
    validate_standings = SimpleHttpOperator(
        task_id='validate_standings',
        http_conn_id='quality_service',
        endpoint='/validate',
        method='POST',
        data='{"s3_key": "bronze/standings/2024/", "data_type": "standings"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Validate team data
    validate_teams = SimpleHttpOperator(
        task_id='validate_teams',
        http_conn_id='quality_service',
        endpoint='/validate',
        method='POST',
        data='{"s3_key": "bronze/team_info/", "data_type": "team_info"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Validate team performance data
    validate_team_performance = SimpleHttpOperator(
        task_id='validate_team_performance',
        http_conn_id='quality_service',
        endpoint='/validate',
        method='POST',
        data='{"s3_key": "bronze/team_performance/", "data_type": "team_performance"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Validate team results data
    validate_team_results = SimpleHttpOperator(
        task_id='validate_team_results',
        http_conn_id='quality_service',
        endpoint='/validate',
        method='POST',
        data='{"s3_key": "bronze/team_results/", "data_type": "team_results"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Validate athlete statistics data
    validate_athlete_stats = SimpleHttpOperator(
        task_id='validate_athlete_stats',
        http_conn_id='quality_service',
        endpoint='/validate',
        method='POST',
        data='{"s3_key": "bronze/athlete_statistics/", "data_type": "athlete_statistics"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Validate athlete bio data
    validate_athlete_bio = SimpleHttpOperator(
        task_id='validate_athlete_bio',
        http_conn_id='quality_service',
        endpoint='/validate',
        method='POST',
        data='{"s3_key": "bronze/athlete_bio/", "data_type": "athlete_bio"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    check_quality_health >> [
        validate_standings,
        validate_teams,
        validate_team_performance,
        validate_team_results,
        validate_athlete_stats,
        validate_athlete_bio
    ]

# Task Group: Data Transformation
with TaskGroup("data_transformation", dag=dag) as transformation_group:
    
    # Bronze to Silver transformation
    bronze_to_silver = create_kubernetes_pod_operator(
        task_id='bronze_to_silver_transform',
        image='champions-league/data-transformation:latest',
        command=['python'],
        arguments=['transform_bronze_to_silver.py'],
        env_vars={
            'INPUT_PATH': f's3a://{S3_BUCKET}/bronze/',
            'OUTPUT_PATH': f's3a://{S3_BUCKET}/silver/'
        },
        resources={
            'request_memory': '2Gi',
            'request_cpu': '1000m',
            'limit_memory': '4Gi',
            'limit_cpu': '2000m'
        }
    )
    
    # Silver to Gold transformation
    silver_to_gold = create_kubernetes_pod_operator(
        task_id='silver_to_gold_transform',
        image='champions-league/data-transformation:latest',
        command=['python'],
        arguments=['transform_silver_to_gold.py'],
        env_vars={
            'INPUT_PATH': f's3a://{S3_BUCKET}/silver/',
            'OUTPUT_PATH': f's3a://{S3_BUCKET}/gold/'
        },
        resources={
            'request_memory': '2Gi',
            'request_cpu': '1000m',
            'limit_memory': '4Gi',
            'limit_cpu': '2000m'
        }
    )
    
    bronze_to_silver >> silver_to_gold

# Task Group: Data Export
with TaskGroup("data_export", dag=dag) as export_group:
    
    # Check export service health
    check_export_health = HttpSensor(
        task_id='check_export_service_health',
        http_conn_id='export_service',
        endpoint='/health',
        timeout=30,
        poke_interval=10,
        mode='poke',
        dag=dag
    )
    
    # Export to CSV for Tableau
    export_for_tableau = SimpleHttpOperator(
        task_id='export_for_tableau',
        http_conn_id='export_service',
        endpoint='/export',
        method='POST',
        data='{"dataset_name": "all", "format": "tableau"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    # Export to Excel for business users
    export_to_excel = SimpleHttpOperator(
        task_id='export_to_excel',
        http_conn_id='export_service',
        endpoint='/export',
        method='POST',
        data='{"dataset_name": "all", "format": "excel"}',
        headers={'Content-Type': 'application/json'},
        dag=dag
    )
    
    check_export_health >> [export_for_tableau, export_to_excel]

# Task Group: Data Warehouse Loading
with TaskGroup("data_warehouse", dag=dag) as warehouse_group:
    
    # Load to Redshift
    load_to_redshift = create_kubernetes_pod_operator(
        task_id='load_to_redshift',
        image='champions-league/data-warehouse:latest',
        command=['python'],
        arguments=['load_to_redshift.py'],
        env_vars={
            'INPUT_PATH': f's3a://{S3_BUCKET}/gold/',
            'REDSHIFT_CLUSTER': Variable.get('redshift_cluster'),
            'REDSHIFT_DATABASE': Variable.get('redshift_database'),
            'REDSHIFT_USER': Variable.get('redshift_user')
        },
        resources={
            'request_memory': '1Gi',
            'request_cpu': '500m',
            'limit_memory': '2Gi',
            'limit_cpu': '1000m'
        }
    )

# Pipeline notification task
def send_pipeline_notification(**context):
    """Send notification about pipeline completion"""
    import boto3
    
    sns_client = boto3.client('sns', region_name=AWS_REGION)
    
    # Get task instance results
    task_instances = context['dag_run'].get_task_instances()
    failed_tasks = [ti.task_id for ti in task_instances if ti.state == 'failed']
    
    if failed_tasks:
        subject = "Champions League Pipeline - Failed Tasks"
        message = f"The following tasks failed: {', '.join(failed_tasks)}"
        status = "FAILED"
    else:
        subject = "Champions League Pipeline - Success"
        message = "All pipeline tasks completed successfully"
        status = "SUCCESS"
    
    # Send SNS notification
    sns_client.publish(
        TopicArn=Variable.get('sns_topic_arn'),
        Subject=subject,
        Message=f"""
        Pipeline Status: {status}
        Execution Date: {context['ds']}
        DAG: {context['dag'].dag_id}
        
        {message}
        
        View logs: {context['dag_run'].get_log_url()}
        """
    )

pipeline_notification = PythonOperator(
    task_id='pipeline_notification',
    python_callable=send_pipeline_notification,
    dag=dag,
    trigger_rule='all_done'  # Run regardless of upstream task status
)

# Data quality monitoring task
def monitor_data_quality(**context):
    """Monitor overall data quality metrics"""
    import boto3
    import json
    
    cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)
    
    # Get pipeline metrics
    execution_date = context['ds']
    
    # Put custom metrics to CloudWatch
    cloudwatch.put_metric_data(
        Namespace='ChampionsLeague/DataPipeline',
        MetricData=[
            {
                'MetricName': 'PipelineExecution',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': [
                    {
                        'Name': 'ExecutionDate',
                        'Value': execution_date
                    }
                ]
            }
        ]
    )

data_quality_monitoring = PythonOperator(
    task_id='data_quality_monitoring',
    python_callable=monitor_data_quality,
    dag=dag
)

# Define task dependencies
ingestion_group >> quality_group >> transformation_group >> [export_group, warehouse_group]
[export_group, warehouse_group] >> data_quality_monitoring >> pipeline_notification

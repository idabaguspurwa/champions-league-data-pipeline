"""
Champions League Data Pipeline DAG
Orchestrates the complete data pipeline using Kubernetes operators
and modern Airflow features.
"""

import pendulum
from typing import List, Dict, Any

# Use the @dag decorator for a cleaner DAG definition
from airflow.decorators import dag, task, task_group

# Operators and sensors remain the same.
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.models import Variable

# --- Configuration (loaded once at the top) ---
NAMESPACE = Variable.get("k8s_namespace", default_var="default")
IMAGE_PULL_POLICY = Variable.get("image_pull_policy", default_var="Always")
AWS_REGION = Variable.get("aws_region", default_var="ap-southeast-1")
S3_BUCKET = Variable.get("s3_bucket", default_var="champions-league-data-lake-pghuqgrt")
SNS_TOPIC_ARN = Variable.get("sns_topic_arn", default_var="arn:aws:sns:ap-southeast-1:665049067659:champions-league-pipeline-notifications")

# Define data for dynamic task generation to reduce repetition
INGESTION_CONFIGS = [
    {"task_id_suffix": "standings", "data": '{"endpoint": "standings", "season": "2024"}'},
    {"task_id_suffix": "team_barcelona", "data": '{"endpoint": "team_info", "team_id": "83"}'},
    {"task_id_suffix": "team_performance_barcelona", "data": '{"endpoint": "team_performance", "team_id": "83"}'},
    {"task_id_suffix": "team_results_barcelona", "data": '{"endpoint": "team_results", "team_id": "83", "season": "2024"}'},
    {"task_id_suffix": "athlete_stats", "data": '{"endpoint": "athlete_statistics", "player_id": "150225"}'},
    {"task_id_suffix": "athlete_bio", "data": '{"endpoint": "athlete_bio", "player_id": "150225"}'},
    {"task_id_suffix": "full_dataset", "data": '{"endpoint": "all", "season": "2024", "team_ids": ["83", "86", "85", "81"], "player_ids": ["150225", "164024", "131921"]}'}
]

VALIDATION_CONFIGS = [
    {"task_id_suffix": "standings", "data": '{"s3_key": "bronze/standings/2024/", "data_type": "standings"}'},
    {"task_id_suffix": "teams", "data": '{"s3_key": "bronze/team_info/", "data_type": "team_info"}'},
    {"task_id_suffix": "team_performance", "data": '{"s3_key": "bronze/team_performance/", "data_type": "team_performance"}'},
    {"task_id_suffix": "team_results", "data": '{"s3_key": "bronze/team_results/", "data_type": "team_results"}'},
    {"task_id_suffix": "athlete_stats", "data": '{"s3_key": "bronze/athlete_statistics/", "data_type": "athlete_statistics"}'},
    {"task_id_suffix": "athlete_bio", "data": '{"s3_key": "bronze/athlete_bio/", "data_type": "athlete_bio"}'}
]

def create_kubernetes_pod_operator(
    task_id: str, image: str, command: list = None, arguments: list = None,
    env_vars: dict = None, resources: dict = None, **kwargs
) -> KubernetesPodOperator:
    """Factory function for a standardized Kubernetes Pod Operator."""
    default_env_vars = {'AWS_REGION': AWS_REGION, 'S3_BUCKET': S3_BUCKET, 'LOG_LEVEL': 'INFO'}
    if env_vars:
        default_env_vars.update(env_vars)
    
    default_resources = {
        'request_memory': '512Mi', 'request_cpu': '250m',
        'limit_memory': '1Gi', 'limit_cpu': '500m'
    }
    if resources:
        default_resources.update(resources)
        
    return KubernetesPodOperator(
        task_id=task_id, name=f"cl-{task_id}", namespace=NAMESPACE, image=image,
        image_pull_policy=IMAGE_PULL_POLICY, cmds=command, arguments=arguments,
        env_vars=default_env_vars, resources=default_resources, get_logs=True,
        is_delete_operator_pod=True, **kwargs
    )

@dag(
    dag_id='champions_league_pipeline_v2',
    start_date=pendulum.datetime(2025, 7, 16, tz="Asia/Jakarta"),
    schedule='0 */6 * * *',  # Every 6 hours.
    catchup=False,
    max_active_runs=1,
    doc_md=__doc__,
    default_args={
        'owner': 'data-engineering-team',
        'depends_on_past': False,
        'email_on_failure': True,
        'email_on_retry': False,
        'retries': 2,
        'retry_delay': pendulum.duration(minutes=5),
    },
    tags=['champions-league', 'data-engineering', 'kubernetes', 'v2'],
)
def champions_league_pipeline():
    """
    ### Champions League Data Pipeline
    This DAG orchestrates the entire data pipeline from ingestion to data warehouse loading,
    utilizing a microservice architecture and running tasks on Kubernetes.
    """

    @task_group(group_id="data_ingestion")
    def ingestion_group():
        check_ingestion_health = HttpSensor(
            task_id='check_ingestion_service_health', http_conn_id='ingestion_service',
            endpoint='/health', timeout=30, poke_interval=10, mode='poke'
        )
        
        ingestion_tasks = []
        for config in INGESTION_CONFIGS:
            task = SimpleHttpOperator(
                task_id=f'ingest_{config["task_id_suffix"]}', http_conn_id='ingestion_service',
                endpoint='/ingest', method='POST', data=config["data"],
                headers={'Content-Type': 'application/json'}
            )
            ingestion_tasks.append(task)
            
        check_ingestion_health >> ingestion_tasks

    @task_group(group_id="data_quality")
    def quality_group():
        check_quality_health = HttpSensor(
            task_id='check_quality_service_health', http_conn_id='quality_service',
            endpoint='/health', timeout=30, poke_interval=10, mode='poke'
        )

        validation_tasks = []
        for config in VALIDATION_CONFIGS:
            task = SimpleHttpOperator(
                task_id=f'validate_{config["task_id_suffix"]}', http_conn_id='quality_service',
                endpoint='/validate', method='POST', data=config["data"],
                headers={'Content-Type': 'application/json'}
            )
            validation_tasks.append(task)

        check_quality_health >> validation_tasks

    @task_group(group_id="data_transformation")
    def transformation_group():
        bronze_to_silver = create_kubernetes_pod_operator(
            task_id='bronze_to_silver_transform', image='champions-league/data-transformation:latest',
            command=['python'], arguments=['transform_bronze_to_silver.py'],
            env_vars={'INPUT_PATH': f's3a://{S3_BUCKET}/bronze/', 'OUTPUT_PATH': f's3a://{S3_BUCKET}/silver/'},
            resources={'request_memory': '2Gi', 'limit_memory': '4Gi', 'request_cpu': '1000m', 'limit_cpu': '2000m'}
        )
        
        silver_to_gold = create_kubernetes_pod_operator(
            task_id='silver_to_gold_transform', image='champions-league/data-transformation:latest',
            command=['python'], arguments=['transform_silver_to_gold.py'],
            env_vars={'INPUT_PATH': f's3a://{S3_BUCKET}/silver/', 'OUTPUT_PATH': f's3a://{S3_BUCKET}/gold/'},
            resources={'request_memory': '2Gi', 'limit_memory': '4Gi', 'request_cpu': '1000m', 'limit_cpu': '2000m'}
        )
        
        bronze_to_silver >> silver_to_gold

    @task_group(group_id="data_export")
    def export_group():
        check_export_health = HttpSensor(
            task_id='check_export_service_health', http_conn_id='export_service',
            endpoint='/health', timeout=30, poke_interval=10, mode='poke'
        )
        
        export_for_tableau = SimpleHttpOperator(
            task_id='export_for_tableau', http_conn_id='export_service', endpoint='/export', method='POST',
            data='{"dataset_name": "all", "format": "tableau"}', headers={'Content-Type': 'application/json'}
        )
        
        export_to_excel = SimpleHttpOperator(
            task_id='export_to_excel', http_conn_id='export_service', endpoint='/export', method='POST',
            data='{"dataset_name": "all", "format": "excel"}', headers={'Content-Type': 'application/json'}
        )
        
        check_export_health >> [export_for_tableau, export_to_excel]

    load_to_redshift = create_kubernetes_pod_operator(
        task_id='load_to_redshift_pod', 
        image='champions-league/data-warehouse:latest',
        command=['python'], 
        arguments=['load_to_redshift.py'],
        env_vars={
            'INPUT_PATH': f's3a://{S3_BUCKET}/gold/',
            'REDSHIFT_CLUSTER': '{{ var.value.redshift_cluster }}',
            'REDSHIFT_DATABASE': '{{ var.value.redshift_database }}',
            'REDSHIFT_USER': '{{ var.value.redshift_user }}'
        },
        resources={'request_memory': '1Gi', 'limit_memory': '2Gi', 'request_cpu': '500m', 'limit_cpu': '1000m'}
    )
    
    @task.kubernetes(
        image="apache/airflow:2.9.2-python3.9",
        name="sns-notification-pod", 
        is_delete_operator_pod=True,
        trigger_rule='all_done'
    )
    
    def pipeline_notification(dag_run=None):
        import boto3
        
        sns_client = boto3.client('sns', region_name=AWS_REGION)
        failed_tasks = [ti.task_id for ti in dag_run.get_task_instances(state='failed')]
        
        status = "FAILED" if failed_tasks else "SUCCESS"
        subject = f"Champions League Pipeline - {status}"
        message_body = f"The following tasks failed: {', '.join(failed_tasks)}" if failed_tasks else "All pipeline tasks completed successfully."

        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN, Subject=subject,
            Message=f"Pipeline Status: {status}\nExecution Date: {dag_run.logical_date.to_date_string()}\n{message_body}"
        )
        return subject

    ingestion_group() >> quality_group() >> transformation_group() >> [export_group(), load_to_redshift] >> pipeline_notification()

champions_league_pipeline()
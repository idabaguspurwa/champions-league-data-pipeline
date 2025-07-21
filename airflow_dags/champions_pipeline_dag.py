"""
Champions League Data Pipeline DAG
Orchestrates the complete data pipeline using Kubernetes operators
and modern Airflow features on self-managed Airflow (EKS).
"""

import pendulum
from typing import List, Dict, Any

from airflow.decorators import dag, task, task_group
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.http.operators.http import HttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.models import Variable
from kubernetes.client import models as k8s

# --- Configuration ---
NAMESPACE = Variable.get("k8s_namespace", default_var="default")
IMAGE_PULL_POLICY = Variable.get("image_pull_policy", default_var="Always")
AWS_REGION = Variable.get("aws_region", default_var="ap-southeast-1")
S3_BUCKET = Variable.get("s3_bucket", default_var="champions-league-data-lake-pghuqgrt")
SNS_TOPIC_ARN = Variable.get("sns_topic_arn", default_var="arn:aws:sns:ap-southeast-1:665049067659:champions-league-pipeline-notifications")
ECR_REGISTRY = Variable.get("ecr_registry", default_var="665049067659.dkr.ecr.ap-southeast-1.amazonaws.com")

# Service account for IRSA (IAM Roles for Service Accounts)
SERVICE_ACCOUNT_NAME = "airflow-worker"  # This should match your IRSA setup

# Define data for dynamic task generation
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
    default_env_vars = {
        'AWS_REGION': AWS_REGION, 
        'S3_BUCKET': S3_BUCKET, 
        'LOG_LEVEL': 'INFO'
    }
    if env_vars:
        default_env_vars.update(env_vars)
    
    # Define default resources
    default_resources = {
        'requests': {'memory': '512Mi', 'cpu': '250m'},
        'limits': {'memory': '1Gi', 'cpu': '500m'}
    }
    if resources:
        default_resources.update(resources)

    # Create the Kubernetes V1ResourceRequirements object
    k8s_resources = k8s.V1ResourceRequirements(**default_resources)
    
    # Use full image path with ECR registry
    full_image = f"{ECR_REGISTRY}/{image}" if not image.startswith(ECR_REGISTRY) else image
        
    return KubernetesPodOperator(
        task_id=task_id,
        name=f"cl-{task_id}",
        namespace=NAMESPACE,
        image=full_image,
        image_pull_policy=IMAGE_PULL_POLICY,
        cmds=command,
        arguments=arguments,
        env_vars=default_env_vars,
        container_resources=k8s_resources,
        get_logs=True,
        is_delete_operator_pod=True,
        service_account_name=SERVICE_ACCOUNT_NAME,  # Add service account for IRSA
        in_cluster=True,  # Since Airflow is running in the same cluster
        config_file=None,  # Use in-cluster config
        **kwargs
    )

@dag(
    dag_id='champions_league_pipeline',
    start_date=pendulum.datetime(2025, 7, 19, tz="Asia/Jakarta"),
    schedule='0 */6 * * *',  # Every 6 hours
    catchup=False,
    max_active_runs=1,
    doc_md=__doc__,
    default_args={
        'owner': 'data-engineering-team',
        'depends_on_past': False,
        'email_on_failure': False,  # Disable email, use SNS instead
        'email_on_retry': False,
        'retries': 2,
        'retry_delay': pendulum.duration(minutes=5),
    },
    tags=['champions-league', 'data-engineering', 'kubernetes'],
)
def champions_league_pipeline():
    """
    ### Champions League Data Pipeline
    This DAG orchestrates the entire data pipeline from ingestion to data warehouse loading,
    utilizing a microservice architecture on EKS.
    """

    @task_group(group_id="data_ingestion")
    def ingestion_group():
        check_ingestion_health = HttpSensor(
            task_id='check_ingestion_service_health', 
            http_conn_id='ingestion_service',
            endpoint='/health', 
            timeout=30, 
            poke_interval=10, 
            mode='poke'
        )
        
        ingestion_tasks = []
        for config in INGESTION_CONFIGS:
            task = HttpOperator(
                task_id=f'ingest_{config["task_id_suffix"]}', 
                http_conn_id='ingestion_service',
                endpoint='/ingest', 
                method='POST', 
                data=config["data"],
                headers={'Content-Type': 'application/json'}
            )
            ingestion_tasks.append(task)
            
        check_ingestion_health >> ingestion_tasks

    @task_group(group_id="data_quality")
    def quality_group():
        check_quality_health = HttpSensor(
            task_id='check_quality_service_health', 
            http_conn_id='quality_service',
            endpoint='/health', 
            timeout=30, 
            poke_interval=10, 
            mode='poke'
        )

        validation_tasks = []
        for config in VALIDATION_CONFIGS:
            task = HttpOperator(
                task_id=f'validate_{config["task_id_suffix"]}', 
                http_conn_id='quality_service',
                endpoint='/validate', 
                method='POST', 
                data=config["data"],
                headers={'Content-Type': 'application/json'}
            )
            validation_tasks.append(task)

        check_quality_health >> validation_tasks

    @task_group(group_id="data_transformation")
    def transformation_group():
        bronze_to_silver = create_kubernetes_pod_operator(
            task_id='bronze_to_silver_transform', 
            image='champions-league/data-transformation:latest',
            command=['python'], 
            arguments=['transform_bronze_to_silver.py'],
            env_vars={
                'INPUT_PATH': f's3://{S3_BUCKET}/bronze/', 
                'OUTPUT_PATH': f's3://{S3_BUCKET}/silver/'
            },
            resources={
                'requests': {'memory': '2Gi', 'cpu': '1000m'},
                'limits': {'memory': '4Gi', 'cpu': '2000m'}
            }
        )
        silver_to_gold = create_kubernetes_pod_operator(
            task_id='silver_to_gold_transform', 
            image='champions-league/data-transformation:latest',
            command=['python'], 
            arguments=['transform_silver_to_gold.py'],
            env_vars={
                'INPUT_PATH': f's3://{S3_BUCKET}/silver/', 
                'OUTPUT_PATH': f's3://{S3_BUCKET}/gold/'
            },
            resources={
                'requests': {'memory': '2Gi', 'cpu': '1000m'},
                'limits': {'memory': '4Gi', 'cpu': '2000m'}
            }
        )
        bronze_to_silver >> silver_to_gold

    @task_group(group_id="data_export")
    def export_group():
        check_export_health = HttpSensor(
            task_id='check_export_service_health', 
            http_conn_id='export_service',
            endpoint='/health', 
            timeout=30, 
            poke_interval=10, 
            mode='poke'
        )
        
        export_for_tableau = HttpOperator(
            task_id='export_for_tableau', 
            http_conn_id='export_service', 
            endpoint='/export', 
            method='POST',
            data='{"dataset_name": "all", "format": "tableau"}', 
            headers={'Content-Type': 'application/json'}
        )
        
        export_to_excel = HttpOperator(
            task_id='export_to_excel', 
            http_conn_id='export_service', 
            endpoint='/export', 
            method='POST',
            data='{"dataset_name": "all", "format": "excel"}', 
            headers={'Content-Type': 'application/json'}
        )
        
        check_export_health >> [export_for_tableau, export_to_excel]

    # Load to Redshift - using environment variables from ConfigMap/Secrets
    load_to_redshift = create_kubernetes_pod_operator(
        task_id='load_to_redshift', 
        image='champions-league/data-warehouse:latest',
        command=['python'], 
        arguments=['load_to_redshift.py'],
        env_vars={
            'INPUT_PATH': f's3://{S3_BUCKET}/gold/',
            'REDSHIFT_CLUSTER': Variable.get('redshift_cluster', 'champions-league-redshift-cluster.ci3rhefolqe6.ap-southeast-1.redshift.amazonaws.com'),
            'REDSHIFT_DATABASE': Variable.get('redshift_database', 'champions_league_db'),
            'REDSHIFT_USER': Variable.get('redshift_user', 'admin')
        },
                resources={
            'requests': {'memory': '1Gi', 'cpu': '500m'},
            'limits': {'memory': '2Gi', 'cpu': '1000m'}
        }
    )
    
    @task
    def pipeline_notification(**context):
        """Send SNS notification about pipeline status"""
        import boto3
        from airflow.exceptions import AirflowException
        
        # Since we're running in EKS with IRSA, boto3 will automatically use the pod's IAM role
        sns_client = boto3.client('sns', region_name=AWS_REGION)
        
        # Get task instances from context
        dag_run = context.get('dag_run')
        task_instances = dag_run.get_task_instances() if dag_run else []
        
        failed_tasks = [ti.task_id for ti in task_instances if ti.state == 'failed']
        execution_date = context.get('execution_date', 'N/A')
        
        status = "FAILED" if failed_tasks else "SUCCESS"
        subject = f"Champions League Pipeline - {status}"
        
        if failed_tasks:
            message_body = f"Failed tasks: {', '.join(failed_tasks)}"
        else:
            message_body = "All pipeline tasks completed successfully."
        
        message = f"""
Pipeline Status: {status}
Execution Date: {execution_date}
DAG Run ID: {dag_run.run_id if dag_run else 'N/A'}
Environment: EKS Self-Managed Airflow

{message_body}

View in Airflow UI: http://aecd4db9d42b348d2913a4971e9551f0-154211990.ap-southeast-1.elb.amazonaws.com/dags/champions_league_pipeline/grid
        """
        
        try:
            response = sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=subject,
                Message=message
            )
            return f"Notification sent successfully: {response['MessageId']}"
        except Exception as e:
            print(f"Failed to send SNS notification: {str(e)}")
            # Don't fail the DAG if notification fails
            return f"Notification failed: {str(e)}"

    # Define the dependency chain
    ingestion = ingestion_group()
    quality = quality_group()
    transformation = transformation_group()
    export = export_group()
    notification = pipeline_notification()

    ingestion >> quality >> transformation >> [export, load_to_redshift] >> notification

# Instantiate the DAG
champions_league_pipeline()
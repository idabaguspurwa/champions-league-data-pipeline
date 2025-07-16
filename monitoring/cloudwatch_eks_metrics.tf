# CloudWatch Monitoring Configuration for Champions League EKS
resource "aws_cloudwatch_dashboard" "champions_league_dashboard" {
  dashboard_name = "${var.project_name}-monitoring-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/EKS", "cluster_failed_request_count", "ClusterName", var.cluster_name],
            [".", "cluster_request_total", ".", "."],
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "EKS Cluster Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ContainerInsights", "pod_cpu_utilization", "ClusterName", var.cluster_name, "Namespace", "champions-league"],
            [".", "pod_memory_utilization", ".", ".", ".", "."],
            [".", "pod_network_rx_bytes", ".", ".", ".", "."],
            [".", "pod_network_tx_bytes", ".", ".", ".", "."],
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Pod Performance Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["ChampionsLeague/DataPipeline", "PipelineExecution", "ExecutionDate", ".*"],
            [".", "DataIngestionSuccess", "Service", "ingestion"],
            [".", "DataQualityCheck", "Service", "quality"],
            [".", "TransformationSuccess", "Service", "transformation"],
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Data Pipeline Metrics"
          period  = 300
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 18
        width  = 12
        height = 6

        properties = {
          query   = "SOURCE '/aws/containerinsights/${var.cluster_name}/application'\n| fields @timestamp, @message\n| filter @message like /ERROR/\n| sort @timestamp desc\n| limit 100"
          region  = var.aws_region
          title   = "Application Error Logs"
          view    = "table"
        }
      }
    ]
  })

  tags = local.common_tags
}

# CloudWatch Alarms

# High CPU utilization alarm
resource "aws_cloudwatch_metric_alarm" "high_cpu_utilization" {
  alarm_name          = "${var.project_name}-high-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "pod_cpu_utilization"
  namespace           = "AWS/ContainerInsights"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EKS pod CPU utilization"
  alarm_actions       = [aws_sns_topic.pipeline_notifications.arn]

  dimensions = {
    ClusterName = var.cluster_name
    Namespace   = "champions-league"
  }

  tags = local.common_tags
}

# High memory utilization alarm
resource "aws_cloudwatch_metric_alarm" "high_memory_utilization" {
  alarm_name          = "${var.project_name}-high-memory-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "pod_memory_utilization"
  namespace           = "AWS/ContainerInsights"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EKS pod memory utilization"
  alarm_actions       = [aws_sns_topic.pipeline_notifications.arn]

  dimensions = {
    ClusterName = var.cluster_name
    Namespace   = "champions-league"
  }

  tags = local.common_tags
}

# Pipeline failure alarm
resource "aws_cloudwatch_metric_alarm" "pipeline_failure" {
  alarm_name          = "${var.project_name}-pipeline-failure"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "PipelineExecution"
  namespace           = "ChampionsLeague/DataPipeline"
  period              = "21600"  # 6 hours
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors data pipeline execution failures"
  alarm_actions       = [aws_sns_topic.pipeline_notifications.arn]
  treat_missing_data  = "breaching"

  tags = local.common_tags
}

# Data ingestion failure alarm
resource "aws_cloudwatch_metric_alarm" "data_ingestion_failure" {
  alarm_name          = "${var.project_name}-data-ingestion-failure"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "DataIngestionSuccess"
  namespace           = "ChampionsLeague/DataPipeline"
  period              = "21600"  # 6 hours
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors data ingestion failures"
  alarm_actions       = [aws_sns_topic.pipeline_notifications.arn]
  treat_missing_data  = "breaching"

  dimensions = {
    Service = "ingestion"
  }

  tags = local.common_tags
}

# Data quality alarm
resource "aws_cloudwatch_metric_alarm" "data_quality_failure" {
  alarm_name          = "${var.project_name}-data-quality-failure"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "DataQualityCheck"
  namespace           = "ChampionsLeague/DataPipeline"
  period              = "21600"  # 6 hours
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors data quality check failures"
  alarm_actions       = [aws_sns_topic.pipeline_notifications.arn]
  treat_missing_data  = "breaching"

  dimensions = {
    Service = "quality"
  }

  tags = local.common_tags
}

# Log Groups for application logs
resource "aws_cloudwatch_log_group" "data_ingestion_logs" {
  name              = "/aws/containerinsights/${var.cluster_name}/application/data-ingestion"
  retention_in_days = 30

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "data_quality_logs" {
  name              = "/aws/containerinsights/${var.cluster_name}/application/data-quality"
  retention_in_days = 30

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "data_transformation_logs" {
  name              = "/aws/containerinsights/${var.cluster_name}/application/data-transformation"
  retention_in_days = 30

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "data_export_logs" {
  name              = "/aws/containerinsights/${var.cluster_name}/application/data-export"
  retention_in_days = 30

  tags = local.common_tags
}

# CloudWatch Insights queries for troubleshooting
resource "aws_cloudwatch_query_definition" "error_analysis" {
  name = "${var.project_name}-error-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.data_ingestion_logs.name,
    aws_cloudwatch_log_group.data_quality_logs.name,
    aws_cloudwatch_log_group.data_transformation_logs.name,
    aws_cloudwatch_log_group.data_export_logs.name,
  ]

  query_string = <<EOF
fields @timestamp, @message, @logStream
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
EOF
}

resource "aws_cloudwatch_query_definition" "performance_analysis" {
  name = "${var.project_name}-performance-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.data_ingestion_logs.name,
    aws_cloudwatch_log_group.data_quality_logs.name,
    aws_cloudwatch_log_group.data_transformation_logs.name,
    aws_cloudwatch_log_group.data_export_logs.name,
  ]

  query_string = <<EOF
fields @timestamp, @message, @logStream
| filter @message like /duration/ or @message like /processing time/
| sort @timestamp desc
| limit 100
EOF
}

# Lambda function for custom metrics
resource "aws_lambda_function" "custom_metrics" {
  filename         = "custom_metrics.zip"
  function_name    = "${var.project_name}-custom-metrics"
  role            = aws_iam_role.lambda_role.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 300

  environment {
    variables = {
      CLUSTER_NAME = var.cluster_name
      NAMESPACE    = "champions-league"
    }
  }

  tags = local.common_tags
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# Lambda execution policy
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      }
    ]
  })
}

# CloudWatch Event Rule to trigger Lambda
resource "aws_cloudwatch_event_rule" "custom_metrics_schedule" {
  name                = "${var.project_name}-custom-metrics-schedule"
  description         = "Trigger custom metrics Lambda function"
  schedule_expression = "rate(5 minutes)"

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.custom_metrics_schedule.name
  target_id = "CustomMetricsLambdaTarget"
  arn       = aws_lambda_function.custom_metrics.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.custom_metrics.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.custom_metrics_schedule.arn
}

# Custom metrics Lambda function code
data "archive_file" "custom_metrics_zip" {
  type        = "zip"
  output_path = "custom_metrics.zip"
  source {
    content = <<EOF
import boto3
import json
import os
from datetime import datetime

def handler(event, context):
    cloudwatch = boto3.client('cloudwatch')
    s3 = boto3.client('s3')
    
    cluster_name = os.environ['CLUSTER_NAME']
    namespace = os.environ['NAMESPACE']
    bucket_name = os.environ.get('S3_BUCKET', 'champions-league-data-lake')
    
    try:
        # Custom metric: Data lake size
        response = s3.list_objects_v2(Bucket=bucket_name)
        total_size = sum(obj['Size'] for obj in response.get('Contents', []))
        
        cloudwatch.put_metric_data(
            Namespace='ChampionsLeague/DataLake',
            MetricData=[
                {
                    'MetricName': 'TotalSizeBytes',
                    'Value': total_size,
                    'Unit': 'Bytes',
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
        
        # Custom metric: File count by layer
        for layer in ['bronze', 'silver', 'gold']:
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix=f'{layer}/')
            file_count = len(response.get('Contents', []))
            
            cloudwatch.put_metric_data(
                Namespace='ChampionsLeague/DataLake',
                MetricData=[
                    {
                        'MetricName': 'FileCount',
                        'Value': file_count,
                        'Unit': 'Count',
                        'Dimensions': [
                            {
                                'Name': 'Layer',
                                'Value': layer
                            }
                        ],
                        'Timestamp': datetime.utcnow()
                    }
                ]
            )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Custom metrics sent successfully')
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
EOF
    filename = "index.py"
  }
}

# Outputs
output "cloudwatch_dashboard_url" {
  description = "URL of the CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.champions_league_dashboard.dashboard_name}"
}

output "cloudwatch_log_groups" {
  description = "CloudWatch log groups created"
  value = {
    ingestion      = aws_cloudwatch_log_group.data_ingestion_logs.name
    quality        = aws_cloudwatch_log_group.data_quality_logs.name
    transformation = aws_cloudwatch_log_group.data_transformation_logs.name
    export         = aws_cloudwatch_log_group.data_export_logs.name
  }
}

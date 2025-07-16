# MWAA (Managed Workflows for Apache Airflow) Environment
resource "aws_mwaa_environment" "main" {
  name              = "${var.project_name}-airflow"
  airflow_version   = "2.10.3"
  environment_class = "mw1.small"
  execution_role_arn = aws_iam_role.mwaa_role.arn

  dag_s3_path               = "dags/"
  max_workers               = 10
  min_workers               = 1
  requirements_s3_path      = "requirements.txt"
  source_bucket_arn         = aws_s3_bucket.mwaa_bucket.arn

  network_configuration {
    security_group_ids = [aws_security_group.mwaa_sg.id]
    subnet_ids         = slice(module.vpc.public_subnets, 0, 2)
  }

  webserver_access_mode = "PUBLIC_ONLY"

  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "INFO"
    }

    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }

    task_logs {
      enabled   = true
      log_level = "INFO"
    }

    webserver_logs {
      enabled   = true
      log_level = "INFO"
    }

    worker_logs {
      enabled   = true
      log_level = "INFO"
    }
  }

  airflow_configuration_options = {
    "core.default_task_retries" = 2
    "core.parallelism"          = 16
    "core.max_active_runs_per_dag" = 1
    "core.max_active_tasks_per_dag" = 4
    "webserver.expose_config"   = "true"
    "webserver.rbac"           = "true"
    "scheduler.dag_dir_list_interval" = 60
    "scheduler.catchup_by_default" = "false"
  }

  depends_on = [
    aws_s3_object.mwaa_requirements,
    aws_s3_object.mwaa_dag,
  ]

  tags = local.common_tags
}

# S3 Bucket for MWAA
resource "aws_s3_bucket" "mwaa_bucket" {
  bucket = "${var.project_name}-mwaa-${random_string.suffix.result}"
  
  tags = merge(local.common_tags, {
    Name        = "MWAA Bucket"
    Description = "Storage for Airflow DAGs and dependencies"
  })
}

resource "aws_s3_bucket_versioning" "mwaa_bucket_versioning" {
  bucket = aws_s3_bucket.mwaa_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mwaa_bucket_encryption" {
  bucket = aws_s3_bucket.mwaa_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "mwaa_bucket_pab" {
  bucket = aws_s3_bucket.mwaa_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload requirements.txt to S3
resource "aws_s3_object" "mwaa_requirements" {
  bucket = aws_s3_bucket.mwaa_bucket.id
  key    = "requirements.txt"
  source = "../requirements.txt"
  etag   = filemd5("../requirements.txt")
}

# Upload DAG file to S3
resource "aws_s3_object" "mwaa_dag" {
  bucket = aws_s3_bucket.mwaa_bucket.id
  key    = "dags/champions_pipeline_dag.py"
  source = "../airflow_dags/champions_pipeline_dag.py"
  etag   = filemd5("../airflow_dags/champions_pipeline_dag.py")
}

# Security Group for MWAA
resource "aws_security_group" "mwaa_sg" {
  name        = "${var.project_name}-mwaa-sg"
  description = "Security group for MWAA environment"
  vpc_id      = module.vpc.vpc_id

  # Allow HTTPS traffic from VPC
  ingress {
    from_port = 443
    to_port   = 443
    protocol  = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }

  # Allow public HTTPS access for webserver
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Self-referencing rule for internal MWAA communication
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

# IAM Role for MWAA
resource "aws_iam_role" "mwaa_role" {
  name = "${var.project_name}-mwaa-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = ["airflow-env.amazonaws.com", "airflow.amazonaws.com"]
        }
      }
    ]
  })

  tags = local.common_tags
}

# IAM Policy for MWAA
resource "aws_iam_policy" "mwaa_policy" {
  name        = "${var.project_name}-mwaa-policy"
  description = "Policy for MWAA execution"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "airflow:PublishMetrics"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject*",
          "s3:GetBucket*",
          "s3:List*"
        ]
        Resource = [
          aws_s3_bucket.mwaa_bucket.arn,
          "${aws_s3_bucket.mwaa_bucket.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject*",
          "s3:PutObject*",
          "s3:DeleteObject*",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:GetLogEvents",
          "logs:GetLogRecord",
          "logs:GetLogGroupFields",
          "logs:GetQueryResults"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:airflow-${var.project_name}-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
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
          "sqs:ChangeMessageVisibility",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ReceiveMessage",
          "sqs:SendMessage"
        ]
        Resource = "arn:aws:sqs:${var.aws_region}:*:airflow-celery-*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey*",
          "kms:Encrypt"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "sqs.${var.aws_region}.amazonaws.com"
          }
        }
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
          "sns:Publish"
        ]
        Resource = aws_sns_topic.pipeline_notifications.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcEndpoints",
          "ec2:DescribeDhcpOptions",
          "ec2:DescribeVpcs",
          "ec2:DescribeSecurityGroups",
          "elasticloadbalancing:DescribeLoadBalancers"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "mwaa_policy_attachment" {
  policy_arn = aws_iam_policy.mwaa_policy.arn
  role       = aws_iam_role.mwaa_role.name
}

# Outputs
output "mwaa_environment_name" {
  description = "Name of the MWAA environment"
  value       = aws_mwaa_environment.main.name
}

output "mwaa_environment_arn" {
  description = "ARN of the MWAA environment"
  value       = aws_mwaa_environment.main.arn
}

output "mwaa_webserver_url" {
  description = "Webserver URL of the MWAA environment"
  value       = aws_mwaa_environment.main.webserver_url
}

output "mwaa_bucket_name" {
  description = "Name of the S3 bucket used by MWAA"
  value       = aws_s3_bucket.mwaa_bucket.bucket
}

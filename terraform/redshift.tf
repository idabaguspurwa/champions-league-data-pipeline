# Redshift Subnet Group
resource "aws_redshift_subnet_group" "main" {
  name       = "${var.project_name}-redshift-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = merge(local.common_tags, {
    Name = "Redshift Subnet Group"
  })
}

# Redshift Parameter Group
resource "aws_redshift_parameter_group" "main" {
  name   = "${var.project_name}-redshift-params"
  family = "redshift-1.0"

  parameter {
    name  = "require_ssl"
    value = "true"
  }

  parameter {
    name  = "enable_user_activity_logging"
    value = "true"
  }

  tags = local.common_tags
}

# Security Group for Redshift
resource "aws_security_group" "redshift_sg" {
  name        = "${var.project_name}-redshift-sg"
  description = "Security group for Redshift cluster"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 5439
    to_port     = 5439
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

# Redshift Cluster
resource "aws_redshift_cluster" "main" {
  cluster_identifier              = local.redshift_cluster_identifier
  database_name                   = "champions_league_db"
  master_username                 = "admin"
  master_password                 = random_password.redshift_password.result
  node_type                       = "ra3.xlplus"
  cluster_type                    = "single-node"
  number_of_nodes                 = 1
  
  # Prevent conflicts with AutoFailover operations
  availability_zone_relocation_enabled = false
  
  # Lifecycle rule to prevent conflicts during modifications
  lifecycle {
    ignore_changes = [
      availability_zone_relocation_enabled,
    ]
  }
  port                           = 5439
  
  vpc_security_group_ids         = [aws_security_group.redshift_sg.id]
  cluster_subnet_group_name      = aws_redshift_subnet_group.main.name
  cluster_parameter_group_name   = aws_redshift_parameter_group.main.name
  
  publicly_accessible            = false
  encrypted                      = true
  skip_final_snapshot           = true
  
  # Automated backup configuration
  automated_snapshot_retention_period = 7
  preferred_maintenance_window        = "sun:05:00-sun:06:00"
  
  depends_on = [
    aws_redshift_subnet_group.main,
    aws_redshift_parameter_group.main,
  ]

  tags = merge(local.common_tags, {
    Name = "Redshift Cluster"
  })
}

# Redshift Logging Configuration (separate resource)
resource "aws_redshift_logging" "main" {
  cluster_identifier   = aws_redshift_cluster.main.cluster_identifier
  log_destination_type = "s3"
  bucket_name         = aws_s3_bucket.redshift_logs.bucket
  s3_key_prefix       = "redshift-logs/"

  depends_on = [
    aws_redshift_cluster.main,
    aws_s3_bucket.redshift_logs,
  ]
}

# Random password for Redshift
resource "random_password" "redshift_password" {
  length      = 16
  special     = true
  min_numeric = 1
  min_upper   = 1
  min_lower   = 1
  min_special = 1
}

# Store Redshift password in Secrets Manager
resource "aws_secretsmanager_secret" "redshift_password" {
  name        = "${var.project_name}/redshift/master-password"
  description = "Master password for Redshift cluster"
  
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "redshift_password" {
  secret_id = aws_secretsmanager_secret.redshift_password.id
  secret_string = jsonencode({
    username = aws_redshift_cluster.main.master_username
    password = random_password.redshift_password.result
    host     = aws_redshift_cluster.main.endpoint
    port     = aws_redshift_cluster.main.port
    database = aws_redshift_cluster.main.database_name
  })
}

# S3 Bucket for Redshift logs
resource "aws_s3_bucket" "redshift_logs" {
  bucket = "${var.project_name}-redshift-logs-${random_string.suffix.result}"
  
  tags = merge(local.common_tags, {
    Name        = "Redshift Logs"
    Description = "Storage for Redshift cluster logs"
  })
}

resource "aws_s3_bucket_versioning" "redshift_logs_versioning" {
  bucket = aws_s3_bucket.redshift_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "redshift_logs_encryption" {
  bucket = aws_s3_bucket.redshift_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "redshift_logs_pab" {
  bucket = aws_s3_bucket.redshift_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket Policy for Redshift logging
resource "aws_s3_bucket_policy" "redshift_logs_policy" {
  bucket = aws_s3_bucket.redshift_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "redshift.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.redshift_logs.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Effect = "Allow"
        Principal = {
          Service = "redshift.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.redshift_logs.arn
      }
    ]
  })
}

# IAM Role for Redshift
resource "aws_iam_role" "redshift_role" {
  name = "${var.project_name}-redshift-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "redshift.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# IAM Policy for Redshift S3 access
resource "aws_iam_policy" "redshift_s3_policy" {
  name        = "${var.project_name}-redshift-s3-policy"
  description = "Policy for Redshift S3 access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.redshift_logs.arn,
          "${aws_s3_bucket.redshift_logs.arn}/*"
        ]
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "redshift_s3_policy_attachment" {
  policy_arn = aws_iam_policy.redshift_s3_policy.arn
  role       = aws_iam_role.redshift_role.name
}

# Outputs
output "redshift_cluster_identifier" {
  description = "Redshift cluster identifier"
  value       = aws_redshift_cluster.main.cluster_identifier
}

output "redshift_cluster_endpoint" {
  description = "Redshift cluster endpoint"
  value       = aws_redshift_cluster.main.endpoint
}

output "redshift_cluster_port" {
  description = "Redshift cluster port"
  value       = aws_redshift_cluster.main.port
}

output "redshift_database_name" {
  description = "Redshift database name"
  value       = aws_redshift_cluster.main.database_name
}

output "redshift_master_username" {
  description = "Redshift master username"
  value       = aws_redshift_cluster.main.master_username
  sensitive   = true
}

output "redshift_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Redshift credentials"
  value       = aws_secretsmanager_secret.redshift_password.arn
}

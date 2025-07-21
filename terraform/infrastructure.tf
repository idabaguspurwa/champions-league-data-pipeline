# Random string for unique resource names
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

# VPC Configuration
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false
  one_nat_gateway_per_az = true
  enable_vpn_gateway = true
  enable_dns_hostnames = true
  enable_dns_support = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpc"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  })

  public_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"           = "1"
  }
}

# S3 Bucket for Data Lake
resource "aws_s3_bucket" "data_lake" {
  bucket = local.s3_bucket_name
  
  tags = merge(local.common_tags, {
    Name        = "Data Lake"
    Description = "Champions League data lake storage"
  })
}

resource "aws_s3_bucket_versioning" "data_lake_versioning" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake_encryption" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data_lake_pab" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket for Terraform State (using existing bucket)
data "aws_s3_bucket" "terraform_state" {
  bucket = "${var.project_name}-terraform-state"
}

resource "aws_s3_bucket_versioning" "terraform_state_versioning" {
  bucket = data.aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state_encryption" {
  bucket = data.aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ECR Repository for container images
resource "aws_ecr_repository" "ingestion_service" {
  name = "${var.project_name}/data-ingestion"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = local.common_tags
}

resource "aws_ecr_repository" "quality_service" {
  name = "${var.project_name}/data-quality"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = local.common_tags
}

resource "aws_ecr_repository" "transformation_service" {
  name = "${var.project_name}/data-transformation"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = local.common_tags
}

resource "aws_ecr_repository" "export_service" {
  name = "${var.project_name}/data-export"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = local.common_tags
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "eks_cluster" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = 7
  
  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "application_logs" {
  name              = "/aws/containerinsights/${var.cluster_name}/application"
  retention_in_days = 30
  
  tags = local.common_tags
}

# SNS Topic for notifications
resource "aws_sns_topic" "pipeline_notifications" {
  name = "${var.project_name}-pipeline-notifications"
  
  tags = local.common_tags
}

# SNS Topic Subscription (replace with your email)
resource "aws_sns_topic_subscription" "email_notification" {
  topic_arn = aws_sns_topic.pipeline_notifications.arn
  protocol  = "email"
  endpoint  = "your-email@example.com"  # Replace with your email
}

# Outputs
output "s3_bucket_name" {
  description = "Name of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.bucket
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.vpc.public_subnets
}

output "ecr_repositories" {
  description = "ECR repository URLs"
  value = {
    ingestion      = aws_ecr_repository.ingestion_service.repository_url
    quality        = aws_ecr_repository.quality_service.repository_url
    transformation = aws_ecr_repository.transformation_service.repository_url
    export         = aws_ecr_repository.export_service.repository_url
  }
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for notifications"
  value       = aws_sns_topic.pipeline_notifications.arn
}

# Data sources for EKS cluster
data "aws_eks_cluster" "cluster" {
  name = var.cluster_name
}

data "aws_eks_cluster_auth" "cluster" {
  name = var.cluster_name
}

# Configure providers to use kubeconfig
provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = "arn:aws:eks:ap-southeast-1:665049067659:cluster/champions-league-cluster"
}

provider "helm" {
  kubernetes {
    config_path    = "~/.kube/config"
    config_context = "arn:aws:eks:ap-southeast-1:665049067659:cluster/champions-league-cluster"
  }
}

# Create namespace for Airflow
resource "kubernetes_namespace" "airflow" {
  metadata {
    name = "airflow"
  }
}

# Create IRSA for Airflow
resource "aws_iam_role" "airflow_irsa" {
  name = "${var.project_name}-airflow-irsa"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.eks.arn
      }
      Condition = {
        StringLike = {
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" : "system:serviceaccount:airflow:airflow-*"
        }
      }
    }]
  })

  tags = local.common_tags
}

# Attach policies to Airflow IRSA
resource "aws_iam_role_policy" "airflow_full_access" {
  name = "airflow-full-access"
  role = aws_iam_role.airflow_irsa.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "s3:*",
          "sns:Publish",
          "logs:*",
          "ecr:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# Generate password for Airflow
resource "random_password" "airflow_admin" {
  length  = 16
  special = false
}

# Manage the Airflow Helm deployment
resource "helm_release" "airflow" {
  name       = "airflow"
  namespace  = "airflow"

  repository = "https://airflow.apache.org"
  chart      = "airflow"
  version    = "1.11.0"

  # You might also need to specify custom values
  # values = [
  #   "${file("path/to/your/airflow-values.yaml")}"
  # ]
}

# Create Kubernetes secret for connections
resource "kubernetes_secret" "airflow_connections" {
  metadata {
    name      = "airflow-connections"
    namespace = kubernetes_namespace.airflow.metadata[0].name
  }

  data = {
    AIRFLOW_CONN_AWS_DEFAULT       = "aws://?region_name=${var.aws_region}&role_arn=${aws_iam_role.airflow_irsa.arn}"
    AIRFLOW_CONN_INGESTION_SERVICE = "http://ingestion-service.default.svc.cluster.local:80"
    AIRFLOW_CONN_QUALITY_SERVICE   = "http://quality-service.default.svc.cluster.local:80"
    AIRFLOW_CONN_EXPORT_SERVICE    = "http://export-service.default.svc.cluster.local:80"
  }

  depends_on = [kubernetes_namespace.airflow]
}

# Create LoadBalancer service for Airflow Web UI
resource "kubernetes_service" "airflow_webui_lb" {
  metadata {
    name      = "airflow-webui-lb"
    namespace = "airflow"
  }

  spec {
    type = "LoadBalancer"

    selector = {
      component = "webserver" # Correct selector for Airflow webserver
      release   = "airflow"
    }

    port {
      protocol    = "TCP"
      port        = 80
      target_port = 8080
    }
  }

  # FIX: Changed from data.helm_release to resource.helm_release
  depends_on = [helm_release.airflow]
}

# Get the LoadBalancer service
data "kubernetes_service" "airflow_webui_lb" {
  metadata {
    name      = "airflow-webui-lb"
    namespace = "airflow"
  }

  depends_on = [kubernetes_service.airflow_webui_lb]
}

# Outputs
output "airflow_namespace" {
  value       = kubernetes_namespace.airflow.metadata[0].name
  description = "Kubernetes namespace for Airflow"
}

output "airflow_status" {
  value = {
    # FIX: Changed all references from data.helm_release to helm_release
    deployed    = helm_release.airflow.status == "deployed"
    version     = helm_release.airflow.version
    app_version = helm_release.airflow.app_version
  }
  description = "Airflow deployment status"
}

output "airflow_loadbalancer_url" {
  value = try(
    "http://${data.kubernetes_service.airflow_webui_lb.status[0].load_balancer[0].ingress[0].hostname}",
    "http://${data.kubernetes_service.airflow_webui_lb.status[0].load_balancer[0].ingress[0].ip}",
    "LoadBalancer pending - check with: kubectl get svc -n airflow"
  )
  description = "Airflow Web UI URL via LoadBalancer"
}

output "airflow_commands" {
  value = {
    check_pods          = "kubectl get pods -n airflow"
    check_svc           = "kubectl get svc -n airflow"
    logs                = "kubectl logs -n airflow -l component=scheduler"
    git_sync_logs       = "kubectl logs -n airflow -l component=scheduler -c git-sync"
    restart_scheduler   = "kubectl rollout restart statefulset airflow-scheduler -n airflow"
    restart_dag_processor = "kubectl rollout restart deployment airflow-dag-processor -n airflow"
  }
  description = "Useful commands for Airflow management"
}

output "airflow_credentials" {
  value = {
    username = "admin"
    password = "admin" # Default password for the chart
  }
  sensitive   = true
  description = "Airflow login credentials"
}

output "git_sync_config" {
  value = {
    repository    = "https://github.com/idabaguspurwa/champions-league-data-pipeline.git"
    branch        = "main"
    dags_path     = "airflow_dags"
    sync_interval = "60 seconds"
  }
  description = "Git-sync configuration for DAGs"
}

output "airflow_irsa_role_arn" {
  value       = aws_iam_role.airflow_irsa.arn
  description = "IAM role ARN for Airflow service account"
}

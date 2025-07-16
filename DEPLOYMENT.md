# Deployment Guide - Champions League Data Engineering Platform

## Prerequisites

### 1. AWS Account Setup
- AWS CLI configured with appropriate permissions
- IAM user with EKS, S3, Redshift, MWAA, ECR permissions
- AWS region set to `ap-southeast-1`

### 2. Local Development Environment
- Docker Desktop installed and running
- kubectl configured for EKS
- Terraform >= 1.0
- Python 3.9+ with pip
- Git configured

### 3. Required Environment Variables
```bash
export AWS_REGION=ap-southeast-1
export AWS_ACCOUNT_ID=your-account-id
export CLUSTER_NAME=champions-league-cluster
export ECR_REGISTRY=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

## Deployment Steps

### Phase 1: Infrastructure Deployment

1. **Clone Repository**
   ```bash
   git clone https://github.com/your-username/champions-league-tracker.git
   cd champions-league-tracker
   ```

2. **Initialize Terraform**
   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

3. **Configure kubectl**
   ```bash
   aws eks update-kubeconfig --region ap-southeast-1 --name champions-league-cluster
   kubectl get nodes
   ```

### Phase 2: Container Images

1. **Build and Push Docker Images**
   ```bash
   # Login to ECR
   aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin ${ECR_REGISTRY}
   
   # Build ingestion service
   docker build -f docker/Dockerfile-ingestion -t ${ECR_REGISTRY}/champions-ingestion:latest .
   docker push ${ECR_REGISTRY}/champions-ingestion:latest
   
   # Build data quality service
   docker build -f docker/Dockerfile-data-quality -t ${ECR_REGISTRY}/champions-data-quality:latest .
   docker push ${ECR_REGISTRY}/champions-data-quality:latest
   
   # Build transformation service
   docker build -f docker/Dockerfile-transformation -t ${ECR_REGISTRY}/champions-transformation:latest .
   docker push ${ECR_REGISTRY}/champions-transformation:latest
   
   # Build export service
   docker build -f docker/Dockerfile-export -t ${ECR_REGISTRY}/champions-export:latest .
   docker push ${ECR_REGISTRY}/champions-export:latest
   ```

### Phase 3: Kubernetes Deployment

1. **Create Namespace**
   ```bash
   kubectl create namespace champions-league
   ```

2. **Deploy ConfigMaps and Secrets**
   ```bash
   kubectl apply -f kubernetes/configmaps/
   kubectl apply -f kubernetes/secrets/
   ```

3. **Deploy Services**
   ```bash
   kubectl apply -f kubernetes/services/
   kubectl apply -f kubernetes/deployments/
   ```

4. **Verify Deployment**
   ```bash
   kubectl get pods -n champions-league
   kubectl get services -n champions-league
   ```

### Phase 4: Airflow Configuration

1. **Upload DAG to S3**
   ```bash
   aws s3 cp airflow_dags/champions_pipeline_dag.py s3://champions-league-mwaa-bucket/dags/
   ```

2. **Verify MWAA Environment**
   ```bash
   aws mwaa get-environment --name champions-league-airflow
   ```

### Phase 5: Database Setup

1. **Create Redshift Tables**
   ```bash
   psql -h your-redshift-cluster.cluster-xyz.ap-southeast-1.redshift.amazonaws.com -U admin -d champions_league -f sql/create_tables.sql
   ```

2. **Grant Permissions**
   ```bash
   psql -h your-redshift-cluster.cluster-xyz.ap-southeast-1.redshift.amazonaws.com -U admin -d champions_league -f sql/grant_permissions.sql
   ```

### Phase 6: Monitoring Setup

1. **Deploy CloudWatch Dashboards**
   ```bash
   aws cloudformation deploy --template-file monitoring/cloudwatch-dashboard.yaml --stack-name champions-league-monitoring
   ```

2. **Configure SNS Topics**
   ```bash
   aws sns create-topic --name champions-league-alerts
   aws sns subscribe --topic-arn arn:aws:sns:ap-southeast-1:${AWS_ACCOUNT_ID}:champions-league-alerts --protocol email --notification-endpoint your-email@example.com
   ```

## Verification Steps

### 1. Health Checks
```bash
# Check service health
kubectl get pods -n champions-league
kubectl logs -f deployment/data-ingestion -n champions-league

# Test API endpoints
curl http://ingestion-service:5000/health
curl http://data-quality-service:5000/health
curl http://export-service:5000/health
```

### 2. Data Pipeline Test
```bash
# Trigger ingestion
curl -X POST http://ingestion-service:5000/ingest

# Check S3 data
aws s3 ls s3://champions-league-data-lake/bronze/

# Check Redshift data
psql -h your-redshift-cluster.cluster-xyz.ap-southeast-1.redshift.amazonaws.com -U admin -d champions_league -c "SELECT COUNT(*) FROM teams;"
```

### 3. Airflow DAG Test
```bash
# Check DAG status
aws mwaa create-cli-token --name champions-league-airflow --region ap-southeast-1
# Use token to access Airflow UI
```

## Configuration Files

### 1. Update Image References
Edit `kubernetes/deployments/` files to use your ECR registry:
```yaml
spec:
  containers:
  - name: ingestion
    image: ${AWS_ACCOUNT_ID}.dkr.ecr.ap-southeast-1.amazonaws.com/champions-ingestion:latest
```

### 2. Update Terraform Variables
Edit `terraform/terraform.tfvars`:
```hcl
aws_region = "ap-southeast-1"
cluster_name = "champions-league-cluster"
environment = "production"
vpc_cidr = "10.0.0.0/16"
```

### 3. Update Airflow Configuration
Edit `airflow_dags/champions_pipeline_dag.py`:
```python
AWS_REGION = "ap-southeast-1"
CLUSTER_NAME = "champions-league-cluster"
NAMESPACE = "champions-league"
```

## Troubleshooting

### Common Issues

1. **EKS Cluster Not Accessible**
   ```bash
   aws eks update-kubeconfig --region ap-southeast-1 --name champions-league-cluster
   kubectl config current-context
   ```

2. **Pods Not Starting**
   ```bash
   kubectl describe pod <pod-name> -n champions-league
   kubectl logs <pod-name> -n champions-league
   ```

3. **ECR Push Failures**
   ```bash
   aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin ${ECR_REGISTRY}
   ```

4. **S3 Access Issues**
   ```bash
   aws s3 ls s3://champions-league-data-lake/
   # Check IAM permissions
   ```

5. **Redshift Connection Issues**
   ```bash
   # Check security group rules
   aws ec2 describe-security-groups --group-ids sg-xyz
   ```

### Log Collection
```bash
# Collect all logs
kubectl logs -l app=data-ingestion -n champions-league
kubectl logs -l app=data-quality -n champions-league
kubectl logs -l app=transformation -n champions-league
kubectl logs -l app=export -n champions-league
```

## Security Considerations

1. **IAM Roles**: Use least privilege principle
2. **Network Security**: VPC, security groups, NACLs
3. **Data Encryption**: At rest and in transit
4. **Secret Management**: AWS Secrets Manager or K8s secrets
5. **Image Security**: Regular vulnerability scanning

## Cost Optimization

1. **EKS**: Use spot instances for non-critical workloads
2. **S3**: Use lifecycle policies for data archiving
3. **Redshift**: Use reserved instances for predictable workloads
4. **CloudWatch**: Set log retention policies

## Maintenance Tasks

1. **Regular Updates**: Keep Docker images updated
2. **Security Patches**: Apply security patches regularly
3. **Monitoring**: Review CloudWatch metrics and alarms
4. **Backup**: Regular backup of configuration and data
5. **Testing**: Regular testing of disaster recovery procedures

## Production Readiness Checklist

- [ ] Infrastructure deployed via Terraform
- [ ] All services deployed and healthy
- [ ] Monitoring and alerting configured
- [ ] Security groups and IAM roles configured
- [ ] Data pipeline tested end-to-end
- [ ] Tableau dashboards configured
- [ ] CI/CD pipeline validated
- [ ] Backup and disaster recovery tested
- [ ] Documentation updated
- [ ] Team training completed

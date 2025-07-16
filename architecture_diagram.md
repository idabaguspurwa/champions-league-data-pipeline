# Champions League Data Engineering Platform - Architecture Diagram

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                AWS Cloud (ap-southeast-1)                               │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              Data Sources                                        │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │   │
│  │  │  ESPN API       │  │  Team Data      │  │  Player Stats   │                 │   │
│  │  │  - Standings    │  │  - Team Info    │  │  - Athlete Data │                 │   │
│  │  │  - Events       │  │  - Performance  │  │  - Statistics   │                 │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                               │
│                                        ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                        EKS Cluster (Kubernetes)                                 │   │
│  │                                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │                         Microservices                                   │   │   │
│  │  │                                                                         │   │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │   │
│  │  │  │  Data Ingestion │  │  Data Quality   │  │  Data Transform │        │   │   │
│  │  │  │  Service        │  │  Service        │  │  Service        │        │   │   │
│  │  │  │  - Flask API    │  │  - Great Expect │  │  - PySpark      │        │   │   │
│  │  │  │  - ESPN API     │  │  - Validation   │  │  - Bronze→Silver│        │   │   │
│  │  │  │  - S3 Bronze    │  │  - Reports      │  │  - Silver→Gold  │        │   │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │   │
│  │  │                                                                         │   │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │   │
│  │  │  │  Data Export    │  │  ConfigMaps     │  │  Secrets        │        │   │   │
│  │  │  │  Service        │  │  - API Config   │  │  - Credentials  │        │   │   │
│  │  │  │  - CSV/Excel    │  │  - App Config   │  │  - DB Passwords │        │   │   │
│  │  │  │  - Tableau      │  │  - GE Config    │  │  - API Keys     │        │   │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                               │
│                                        ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           Data Storage Layer                                    │   │
│  │                                                                                 │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │   │
│  │  │  S3 Data Lake   │  │  Amazon Redshift│  │  ECR Registry   │                │   │
│  │  │  - Bronze Layer │  │  - Data Warehouse│  │  - Docker Images│                │   │
│  │  │  - Silver Layer │  │  - Star Schema   │  │  - Versioned    │                │   │
│  │  │  - Gold Layer   │  │  - Analytics    │  │  - Secured      │                │   │
│  │  │  - Exports      │  │  - Tableau      │  │  - Scanned      │                │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                               │
│                                        ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         Workflow Orchestration                                  │   │
│  │                                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │                    MWAA (Apache Airflow)                                │   │   │
│  │  │                                                                         │   │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │   │
│  │  │  │  Data Ingestion │  │  Data Quality   │  │  Data Transform │        │   │   │
│  │  │  │  Task Group     │  │  Task Group     │  │  Task Group     │        │   │   │
│  │  │  │  - API Calls    │  │  - Validation   │  │  - K8s Jobs     │        │   │   │
│  │  │  │  - Health Check │  │  - Reports      │  │  - Spark Tasks  │        │   │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │   │
│  │  │                                                                         │   │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │   │
│  │  │  │  Data Export    │  │  Data Warehouse │  │  Notifications  │        │   │   │
│  │  │  │  Task Group     │  │  Task Group     │  │  Task Group     │        │   │   │
│  │  │  │  - CSV Export   │  │  - Redshift     │  │  - SNS Alerts   │        │   │   │
│  │  │  │  - Tableau      │  │  - Data Loading │  │  - Monitoring   │        │   │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                               │
│                                        ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                      Monitoring and Observability                               │   │
│  │                                                                                 │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │   │
│  │  │  CloudWatch     │  │  SNS            │  │  Lambda         │                │   │
│  │  │  - Metrics      │  │  - Notifications│  │  - Custom       │                │   │
│  │  │  - Logs         │  │  - Alerts       │  │  - Metrics      │                │   │
│  │  │  - Dashboards   │  │  - Email        │  │  - Monitoring   │                │   │
│  │  │  - Alarms       │  │  - Slack        │  │  - Automation   │                │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                               │
│                                        ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         CI/CD Pipeline                                          │   │
│  │                                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │                      GitHub Actions                                     │   │   │
│  │  │                                                                         │   │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │   │
│  │  │  │  Code Quality   │  │  Build & Push   │  │  Deploy to EKS  │        │   │   │
│  │  │  │  - Unit Tests   │  │  - Docker Build │  │  - K8s Deploy   │        │   │   │
│  │  │  │  - Lint/Format  │  │  - ECR Push     │  │  - Rolling      │        │   │   │
│  │  │  │  - Security     │  │  - Versioning   │  │  - Health Check │        │   │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │   │
│  │  │                                                                         │   │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │   │
│  │  │  │  DAG Deployment │  │  Infrastructure │  │  Notifications  │        │   │   │
│  │  │  │  - Airflow DAG  │  │  - Terraform    │  │  - Slack/Email  │        │   │   │
│  │  │  │  - Validation   │  │  - Plan/Apply   │  │  - Status       │        │   │   │
│  │  │  │  - S3 Upload    │  │  - Drift Check  │  │  - Alerts       │        │   │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                               │
│                                        ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                      Visualization and Analytics                                │   │
│  │                                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │                         Tableau                                         │   │   │
│  │  │                                                                         │   │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │   │
│  │  │  │  Competition    │  │  Team           │  │  Player         │        │   │   │
│  │  │  │  Overview       │  │  Performance    │  │  Analytics      │        │   │   │
│  │  │  │  - Standings    │  │  - Metrics      │  │  - Statistics   │        │   │   │
│  │  │  │  - Groups       │  │  - Trends       │  │  - Demographics │        │   │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │   │
│  │  │                                                                         │   │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │   │
│  │  │  │  Match Analysis │  │  Real-time      │  │  Executive      │        │   │   │
│  │  │  │  - Results      │  │  Dashboards     │  │  Summary        │        │   │   │
│  │  │  │  - Fixtures     │  │  - Live Data    │  │  - KPIs         │        │   │   │
│  │  │  │  - Venues       │  │  - Alerts       │  │  - Reports      │        │   │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         Infrastructure as Code                                  │   │
│  │                                                                                 │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │   │
│  │  │  Terraform      │  │  State Management│  │  Resource       │                │   │
│  │  │  - EKS Cluster  │  │  - S3 Backend    │  │  - Tagging      │                │   │
│  │  │  - VPC/Subnets  │  │  - State Lock    │  │  - Cost Opt     │                │   │
│  │  │  - S3/Redshift  │  │  - Versioning    │  │  - Security     │                │   │
│  │  │  - MWAA/IAM     │  │  - Backup        │  │  - Compliance   │                │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Data Ingestion**: ESP API → EKS Ingestion Service → S3 Bronze
2. **Data Quality**: S3 Bronze → EKS Quality Service → Validation Reports
3. **Data Transformation**: S3 Bronze → EKS Spark Jobs → S3 Silver → S3 Gold
4. **Data Export**: S3 Gold → EKS Export Service → CSV/Excel/Tableau
5. **Data Warehouse**: S3 Gold → Redshift → Tableau Dashboards
6. **Orchestration**: Airflow DAG → Kubernetes Pod Operators → Services
7. **Monitoring**: CloudWatch → Metrics/Logs → Alarms → SNS → Notifications

## Key Features

- **Cloud-Native**: Full AWS EKS deployment with Kubernetes-native patterns
- **Scalable**: Auto-scaling based on demand and resource utilization
- **Fault-Tolerant**: Health checks, retries, and circuit breakers
- **Secure**: IAM roles, VPC, encryption at rest and in transit
- **Observable**: Comprehensive monitoring, logging, and alerting
- **Automated**: CI/CD pipeline with infrastructure as code
- **Cost-Optimized**: Spot instances, auto-scaling, and resource limits

## Technology Stack

- **Container Orchestration**: Amazon EKS (Kubernetes)
- **Data Processing**: Apache Spark (PySpark)
- **Workflow Orchestration**: Apache Airflow (MWAA)
- **Data Storage**: Amazon S3, Amazon Redshift
- **Monitoring**: CloudWatch, SNS, Lambda
- **CI/CD**: GitHub Actions
- **Infrastructure**: Terraform
- **Visualization**: Tableau
- **Languages**: Python, SQL, YAML, HCL

# Champions League Data Engineering Platform

A production-grade, cloud-native data engineering platform for Champions League analytics using AWS EKS, Kubernetes, Airflow (MWAA), and Tableau.

## Architecture Overview

This project implements a complete data engineering pipeline with the following components:

- **Data Ingestion Service**: Containerized microservice to fetch Champions League data from RapidAPI
- **Data Quality Validation**: Great Expectations-based validation service
- **Data Transformation**: PySpark-based ETL jobs for Bronze → Silver → Gold data layers
- **Data Export Service**: Service to export processed data to various formats
- **Workflow Orchestration**: Apache Airflow (MWAA) with Kubernetes operators
- **Storage**: S3 for data lake, Redshift for data warehouse
- **Infrastructure**: Terraform for IaC, EKS for container orchestration
- **CI/CD**: GitHub Actions for automated deployments
- **Monitoring**: CloudWatch and optional Grafana
- **Visualization**: Tableau dashboards

## Data Sources

The platform uses the **UEFA Champions League API** from RapidAPI, which provides comprehensive data including:

- **Standings**: Group stage and knockout phase standings
- **Team Information**: Team details, logos, and basic information
- **Team Performance**: Performance metrics and statistics
- **Team Results**: Match results and fixtures
- **Athlete Statistics**: Player performance statistics
- **Athlete Bio**: Player biographical information
- **Athlete Season Stats**: Historical season performance
- **Athlete Overview**: Player overview and career highlights

### API Endpoints Used:
- `/standingsv2` - Competition standings
- `/team/info` - Team information
- `/team/perfomance` - Team performance metrics
- `/team/results` - Match results
- `/athlete/statistic` - Player statistics
- `/athlete/bio` - Player biography
- `/athlete/season` - Season statistics
- `/athlete/overview` - Player overview

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and update the following variables:

```bash
# RapidAPI Configuration
RAPIDAPI_KEY=your_rapidapi_key_here
RAPIDAPI_HOST=uefa-champions-league1.p.rapidapi.com

# API Configuration
API_BASE_URL=https://uefa-champions-league1.p.rapidapi.com
RATE_LIMIT=100
TIMEOUT=30
RETRY_ATTEMPTS=3

# AWS Configuration
AWS_REGION=ap-southeast-1
S3_BUCKET=champions-league-data-lake

# Database Configuration
REDSHIFT_HOST=your-redshift-cluster.amazonaws.com
REDSHIFT_DB=champions_league
REDSHIFT_USER=admin
REDSHIFT_PASSWORD=your_password_here
```

### Kubernetes Secrets

Create the API credentials secret:
```bash
kubectl create secret generic api-credentials \
  --from-literal=rapidapi_key=your_rapidapi_key_here \
  --namespace=champions-league
```

## Project Structure

```
├── README.md
├── architecture_diagram.png
├── requirements.txt
├── kubernetes/
│   ├── deployments/
│   ├── services/
│   ├── configmaps/
│   └── jobs/
├── lambda/
├── airflow_dags/
├── data_quality/
├── transformations/
├── terraform/
├── docker/
├── ci_cd/
├── monitoring/
├── visualizations/
└── sql/
```

## Quick Start

1. **Prerequisites**:
   - AWS CLI configured
   - kubectl installed
   - Terraform installed
   - Docker Desktop running

2. **Infrastructure Setup**:
   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

3. **Deploy to EKS**:
   ```bash
   kubectl apply -f kubernetes/
   ```

4. **Setup Airflow DAGs**:
   - Upload DAGs to MWAA environment
   - Configure connections and variables

5. **Run Pipeline**:
   - Trigger DAG in Airflow UI
   - Monitor execution in CloudWatch

## Services

### Data Ingestion Service
- Fetches Champions League data from APIs
- Stores raw data in S3 Bronze layer
- Runs as Kubernetes deployment

### Data Quality Service
- Validates data quality using Great Expectations
- Generates data quality reports
- Fails pipeline on critical data issues

### Data Transformation Service
- PySpark-based transformations
- Bronze → Silver → Gold data layers
- Runs as Kubernetes jobs

### Data Export Service
- Exports processed data to CSV/Excel
- Supports multiple output formats
- Stores in S3 for Tableau consumption

## Monitoring and Logging

- CloudWatch for metrics and logs
- Kubernetes native monitoring
- Custom dashboards for pipeline health

## Visualization

- Tableau dashboards connected to Redshift
- Real-time Champions League analytics
- Performance metrics and KPIs

## Contributing

1. Fork the repository
2. Create feature branch
3. Submit pull request
4. Ensure all tests pass

## License

MIT License

"""
Data Export Service for Champions League Data
Exports processed data to various formats for consumption
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from io import StringIO, BytesIO

import boto3
import pandas as pd
import structlog
from flask import Flask, jsonify, request, send_file
from botocore.exceptions import ClientError
import pyarrow.parquet as pq
import pyarrow as pa

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = Flask(__name__)

class DataExportService:
    """Service to export processed data to various formats"""
    
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'ap-southeast-1'))
        self.bucket_name = os.getenv('S3_BUCKET', 'champions-league-data-lake')
        self.gold_path = "gold/"
        self.export_path = "exports/"
        
    def read_parquet_from_s3(self, s3_key: str) -> pd.DataFrame:
        """Read Parquet file from S3 and return as DataFrame"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            parquet_buffer = BytesIO(response['Body'].read())
            df = pd.read_parquet(parquet_buffer)
            
            logger.info(
                "Successfully read parquet from S3",
                s3_key=s3_key,
                rows=len(df),
                columns=len(df.columns)
            )
            return df
            
        except Exception as e:
            logger.error("Failed to read parquet from S3", s3_key=s3_key, error=str(e))
            raise
            
    def list_s3_objects(self, prefix: str) -> List[str]:
        """List objects in S3 with given prefix"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
            
        except Exception as e:
            logger.error("Failed to list S3 objects", prefix=prefix, error=str(e))
            raise
            
    def export_to_csv(self, dataset_name: str, output_format: str = 'csv') -> str:
        """Export Gold dataset to CSV format"""
        try:
            # Find parquet files for the dataset
            parquet_files = self.list_s3_objects(f"{self.gold_path}{dataset_name}/")
            parquet_files = [f for f in parquet_files if f.endswith('.parquet')]
            
            if not parquet_files:
                raise ValueError(f"No parquet files found for dataset: {dataset_name}")
                
            # Read all parquet files and combine
            dfs = []
            for parquet_file in parquet_files:
                df = self.read_parquet_from_s3(parquet_file)
                dfs.append(df)
                
            # Combine all DataFrames
            combined_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
            
            # Convert to CSV
            csv_buffer = StringIO()
            combined_df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()
            
            # Generate export filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            export_key = f"{self.export_path}{dataset_name}/{dataset_name}_{timestamp}.csv"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=export_key,
                Body=csv_content.encode('utf-8'),
                ContentType='text/csv',
                ServerSideEncryption='AES256'
            )
            
            logger.info(
                "Successfully exported to CSV",
                dataset_name=dataset_name,
                export_key=export_key,
                rows=len(combined_df),
                columns=len(combined_df.columns)
            )
            
            return export_key
            
        except Exception as e:
            logger.error("CSV export failed", dataset_name=dataset_name, error=str(e))
            raise
            
    def export_to_excel(self, dataset_name: str) -> str:
        """Export Gold dataset to Excel format"""
        try:
            # Find parquet files for the dataset
            parquet_files = self.list_s3_objects(f"{self.gold_path}{dataset_name}/")
            parquet_files = [f for f in parquet_files if f.endswith('.parquet')]
            
            if not parquet_files:
                raise ValueError(f"No parquet files found for dataset: {dataset_name}")
                
            # Read all parquet files and combine
            dfs = []
            for parquet_file in parquet_files:
                df = self.read_parquet_from_s3(parquet_file)
                dfs.append(df)
                
            # Combine all DataFrames
            combined_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
            
            # Convert to Excel
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                combined_df.to_excel(writer, sheet_name=dataset_name, index=False)
                
            excel_content = excel_buffer.getvalue()
            
            # Generate export filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            export_key = f"{self.export_path}{dataset_name}/{dataset_name}_{timestamp}.xlsx"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=export_key,
                Body=excel_content,
                ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ServerSideEncryption='AES256'
            )
            
            logger.info(
                "Successfully exported to Excel",
                dataset_name=dataset_name,
                export_key=export_key,
                rows=len(combined_df),
                columns=len(combined_df.columns)
            )
            
            return export_key
            
        except Exception as e:
            logger.error("Excel export failed", dataset_name=dataset_name, error=str(e))
            raise
            
    def export_to_json(self, dataset_name: str) -> str:
        """Export Gold dataset to JSON format"""
        try:
            # Find parquet files for the dataset
            parquet_files = self.list_s3_objects(f"{self.gold_path}{dataset_name}/")
            parquet_files = [f for f in parquet_files if f.endswith('.parquet')]
            
            if not parquet_files:
                raise ValueError(f"No parquet files found for dataset: {dataset_name}")
                
            # Read all parquet files and combine
            dfs = []
            for parquet_file in parquet_files:
                df = self.read_parquet_from_s3(parquet_file)
                dfs.append(df)
                
            # Combine all DataFrames
            combined_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
            
            # Convert to JSON
            json_data = combined_df.to_dict(orient='records')
            
            # Add metadata
            export_data = {
                'metadata': {
                    'dataset_name': dataset_name,
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'record_count': len(json_data),
                    'columns': list(combined_df.columns)
                },
                'data': json_data
            }
            
            json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
            
            # Generate export filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            export_key = f"{self.export_path}{dataset_name}/{dataset_name}_{timestamp}.json"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=export_key,
                Body=json_content.encode('utf-8'),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            logger.info(
                "Successfully exported to JSON",
                dataset_name=dataset_name,
                export_key=export_key,
                rows=len(combined_df),
                columns=len(combined_df.columns)
            )
            
            return export_key
            
        except Exception as e:
            logger.error("JSON export failed", dataset_name=dataset_name, error=str(e))
            raise
            
    def get_available_datasets(self) -> List[str]:
        """Get list of available Gold datasets"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=self.gold_path,
                Delimiter='/'
            )
            
            datasets = []
            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    dataset_name = prefix['Prefix'].replace(self.gold_path, '').rstrip('/')
                    datasets.append(dataset_name)
                    
            return datasets
            
        except Exception as e:
            logger.error("Failed to get available datasets", error=str(e))
            raise
            
    def export_all_datasets(self, output_format: str = 'csv') -> Dict[str, str]:
        """Export all available datasets to specified format"""
        try:
            datasets = self.get_available_datasets()
            results = {}
            
            for dataset in datasets:
                try:
                    if output_format.lower() == 'csv':
                        export_key = self.export_to_csv(dataset)
                    elif output_format.lower() == 'excel':
                        export_key = self.export_to_excel(dataset)
                    elif output_format.lower() == 'json':
                        export_key = self.export_to_json(dataset)
                    else:
                        raise ValueError(f"Unsupported format: {output_format}")
                        
                    results[dataset] = export_key
                    
                except Exception as e:
                    logger.error("Dataset export failed", dataset=dataset, error=str(e))
                    results[dataset] = f"Error: {str(e)}"
                    
            return results
            
        except Exception as e:
            logger.error("Bulk export failed", error=str(e))
            raise
            
    def create_tableau_extract(self, dataset_name: str) -> str:
        """Create Tableau-optimized extract"""
        try:
            # For now, we'll export as CSV which Tableau can consume
            # In a production environment, you might want to use Tableau's SDK
            export_key = self.export_to_csv(dataset_name)
            
            # Create a copy with tableau-specific naming
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            tableau_key = f"{self.export_path}tableau/{dataset_name}_tableau_{timestamp}.csv"
            
            # Copy the file
            copy_source = {'Bucket': self.bucket_name, 'Key': export_key}
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=tableau_key
            )
            
            logger.info(
                "Created Tableau extract",
                dataset_name=dataset_name,
                tableau_key=tableau_key
            )
            
            return tableau_key
            
        except Exception as e:
            logger.error("Tableau extract creation failed", dataset_name=dataset_name, error=str(e))
            raise

# Initialize service
export_service = DataExportService()

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'champions-league-export'
    })

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    try:
        # Check S3 connectivity
        export_service.s3_client.head_bucket(Bucket=export_service.bucket_name)
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@app.route('/datasets')
def list_datasets():
    """List available datasets"""
    try:
        datasets = export_service.get_available_datasets()
        return jsonify({
            'datasets': datasets,
            'count': len(datasets),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/export', methods=['POST'])
def export_data():
    """Export data to specified format"""
    try:
        request_data = request.get_json()
        dataset_name = request_data.get('dataset_name')
        output_format = request_data.get('format', 'csv').lower()
        
        if not dataset_name:
            return jsonify({'error': 'dataset_name is required'}), 400
            
        if dataset_name == 'all':
            results = export_service.export_all_datasets(output_format)
            return jsonify({
                'status': 'completed',
                'results': results,
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            if output_format == 'csv':
                export_key = export_service.export_to_csv(dataset_name)
            elif output_format == 'excel':
                export_key = export_service.export_to_excel(dataset_name)
            elif output_format == 'json':
                export_key = export_service.export_to_json(dataset_name)
            elif output_format == 'tableau':
                export_key = export_service.create_tableau_extract(dataset_name)
            else:
                return jsonify({'error': f'Unsupported format: {output_format}'}), 400
                
            return jsonify({
                'status': 'completed',
                'export_key': export_key,
                'dataset_name': dataset_name,
                'format': output_format,
                'timestamp': datetime.utcnow().isoformat()
            })
            
    except Exception as e:
        logger.error("Export request failed", error=str(e))
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

if __name__ == '__main__':
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(level=getattr(logging, log_level))
    
    app.run(host='0.0.0.0', port=8080, debug=False)

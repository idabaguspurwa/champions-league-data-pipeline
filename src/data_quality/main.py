"""
Data Quality Service for Champions League Data
Validates data quality using Great Expectations
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

import boto3
import pandas as pd
import structlog
from flask import Flask, jsonify, request
from great_expectations import DataContext
from great_expectations.core.batch import RuntimeBatchRequest
from great_expectations.checkpoint import SimpleCheckpoint
from great_expectations.exceptions import ValidationError

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

class DataQualityService:
    """Service to validate data quality using Great Expectations"""
    
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'ap-southeast-1'))
        self.bucket_name = os.getenv('S3_BUCKET', 'champions-league-data-lake')
        self.ge_context = None
        self.initialize_great_expectations()
        
    def initialize_great_expectations(self):
        """Initialize Great Expectations context"""
        try:
            # Check if GE context exists, if not create it
            if not Path('/app/great_expectations').exists():
                self.ge_context = DataContext.create('/app/great_expectations')
                logger.info("Created new Great Expectations context")
            else:
                self.ge_context = DataContext('/app/great_expectations')
                logger.info("Loaded existing Great Expectations context")
                
        except Exception as e:
            logger.error("Failed to initialize Great Expectations", error=str(e))
            raise
            
    def validate_standings_data(self, data: Dict) -> Dict:
        """Validate standings data structure and content"""
        try:
            # Convert to DataFrame for validation
            if 'data' in data:
                df = pd.json_normalize(data['data'])
            else:
                df = pd.json_normalize(data)
                
            # Create batch request
            batch_request = RuntimeBatchRequest(
                datasource_name="pandas_datasource",
                data_connector_name="default_runtime_data_connector",
                data_asset_name="standings_data",
                runtime_parameters={"batch_data": df},
                batch_identifiers={"default_identifier_name": "standings_batch"}
            )
            
            # Define expectations
            expectations = [
                {
                    "expectation_type": "expect_table_row_count_to_be_between",
                    "kwargs": {"min_value": 1, "max_value": 100}
                },
                {
                    "expectation_type": "expect_column_to_exist",
                    "kwargs": {"column": "data.id"}
                },
                {
                    "expectation_type": "expect_column_to_exist",
                    "kwargs": {"column": "data.name"}
                },
                {
                    "expectation_type": "expect_column_values_to_not_be_null",
                    "kwargs": {"column": "data.id"}
                }
            ]
            
            # Run validations
            results = self.run_validations(batch_request, expectations, "standings")
            
            return {
                "data_type": "standings",
                "validation_results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Standings validation failed", error=str(e))
            return {
                "data_type": "standings",
                "validation_results": {"success": False, "error": str(e)},
                "timestamp": datetime.utcnow().isoformat()
            }
            
    def validate_teams_data(self, data: Dict) -> Dict:
        """Validate teams data structure and content"""
        try:
            # Convert to DataFrame for validation
            if 'data' in data:
                df = pd.json_normalize(data['data'])
            else:
                df = pd.json_normalize(data)
                
            # Create batch request
            batch_request = RuntimeBatchRequest(
                datasource_name="pandas_datasource",
                data_connector_name="default_runtime_data_connector",
                data_asset_name="teams_data",
                runtime_parameters={"batch_data": df},
                batch_identifiers={"default_identifier_name": "teams_batch"}
            )
            
            # Define expectations
            expectations = [
                {
                    "expectation_type": "expect_table_row_count_to_be_between",
                    "kwargs": {"min_value": 1, "max_value": 50}
                },
                {
                    "expectation_type": "expect_column_to_exist",
                    "kwargs": {"column": "data.id"}
                },
                {
                    "expectation_type": "expect_column_to_exist",
                    "kwargs": {"column": "data.name"}
                },
                {
                    "expectation_type": "expect_column_values_to_not_be_null",
                    "kwargs": {"column": "data.id"}
                },
                {
                    "expectation_type": "expect_column_values_to_not_be_null",
                    "kwargs": {"column": "data.name"}
                }
            ]
            
            # Run validations
            results = self.run_validations(batch_request, expectations, "teams")
            
            return {
                "data_type": "teams",
                "validation_results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Teams validation failed", error=str(e))
            return {
                "data_type": "teams",
                "validation_results": {"success": False, "error": str(e)},
                "timestamp": datetime.utcnow().isoformat()
            }
            
    def validate_athletes_data(self, data: Dict) -> Dict:
        """Validate athletes data structure and content"""
        try:
            # Convert to DataFrame for validation
            if 'data' in data:
                df = pd.json_normalize(data['data'])
            else:
                df = pd.json_normalize(data)
                
            # Create batch request
            batch_request = RuntimeBatchRequest(
                datasource_name="pandas_datasource",
                data_connector_name="default_runtime_data_connector",
                data_asset_name="athletes_data",
                runtime_parameters={"batch_data": df},
                batch_identifiers={"default_identifier_name": "athletes_batch"}
            )
            
            # Define expectations
            expectations = [
                {
                    "expectation_type": "expect_table_row_count_to_be_between",
                    "kwargs": {"min_value": 1, "max_value": 1000}
                },
                {
                    "expectation_type": "expect_column_to_exist",
                    "kwargs": {"column": "data.id"}
                },
                {
                    "expectation_type": "expect_column_values_to_not_be_null",
                    "kwargs": {"column": "data.id"}
                }
            ]
            
            # Run validations
            results = self.run_validations(batch_request, expectations, "athletes")
            
            return {
                "data_type": "athletes",
                "validation_results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Athletes validation failed", error=str(e))
            return {
                "data_type": "athletes",
                "validation_results": {"success": False, "error": str(e)},
                "timestamp": datetime.utcnow().isoformat()
            }
            
    def run_validations(self, batch_request: RuntimeBatchRequest, expectations: List[Dict], data_type: str) -> Dict:
        """Run Great Expectations validations"""
        try:
            # Create expectation suite
            suite_name = f"{data_type}_suite"
            suite = self.ge_context.create_expectation_suite(
                expectation_suite_name=suite_name,
                overwrite_existing=True
            )
            
            # Add expectations to suite
            for expectation in expectations:
                suite.add_expectation(expectation)
                
            # Save suite
            self.ge_context.save_expectation_suite(suite)
            
            # Create and run checkpoint
            checkpoint_config = {
                "name": f"{data_type}_checkpoint",
                "config_version": 1.0,
                "template_name": None,
                "module_name": "great_expectations.checkpoint",
                "class_name": "SimpleCheckpoint",
                "run_name_template": "%Y%m%d-%H%M%S",
                "expectation_suite_name": suite_name,
                "batch_request": batch_request,
                "action_list": [
                    {
                        "name": "store_validation_result",
                        "action": {"class_name": "StoreValidationResultAction"},
                    }
                ],
            }
            
            checkpoint = SimpleCheckpoint(
                f"{data_type}_checkpoint",
                self.ge_context,
                **checkpoint_config
            )
            
            # Run checkpoint
            results = checkpoint.run()
            
            # Extract validation results
            validation_result = results.list_validation_results()[0]
            
            return {
                "success": validation_result.success,
                "statistics": validation_result.statistics,
                "results": [
                    {
                        "expectation_type": result.expectation_config.expectation_type,
                        "success": result.success,
                        "result": result.result
                    }
                    for result in validation_result.results
                ]
            }
            
        except Exception as e:
            logger.error("Validation execution failed", error=str(e))
            return {"success": False, "error": str(e)}
            
    def validate_s3_file(self, s3_key: str) -> Dict:
        """Validate a file from S3"""
        try:
            # Download file from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            data = json.loads(response['Body'].read())
            
            # Determine data type from S3 key
            if 'standings' in s3_key:
                return self.validate_standings_data(data)
            elif 'teams' in s3_key:
                return self.validate_teams_data(data)
            elif 'athletes' in s3_key:
                return self.validate_athletes_data(data)
            else:
                return {
                    "data_type": "unknown",
                    "validation_results": {"success": False, "error": "Unknown data type"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("S3 file validation failed", s3_key=s3_key, error=str(e))
            return {
                "data_type": "unknown",
                "validation_results": {"success": False, "error": str(e)},
                "timestamp": datetime.utcnow().isoformat()
            }

# Initialize service
data_quality_service = DataQualityService()

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'champions-league-data-quality'
    })

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    try:
        # Check S3 connectivity
        data_quality_service.s3_client.head_bucket(Bucket=data_quality_service.bucket_name)
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

@app.route('/validate', methods=['POST'])
def validate_data():
    """Validate data quality"""
    try:
        request_data = request.get_json()
        
        if 's3_key' in request_data:
            # Validate S3 file
            results = data_quality_service.validate_s3_file(request_data['s3_key'])
        elif 'data' in request_data:
            # Validate provided data
            data_type = request_data.get('data_type', 'unknown')
            data = request_data['data']
            
            if data_type == 'standings':
                results = data_quality_service.validate_standings_data(data)
            elif data_type == 'teams':
                results = data_quality_service.validate_teams_data(data)
            elif data_type == 'athletes':
                results = data_quality_service.validate_athletes_data(data)
            else:
                results = {
                    "data_type": data_type,
                    "validation_results": {"success": False, "error": "Unknown data type"},
                    "timestamp": datetime.utcnow().isoformat()
                }
        else:
            return jsonify({'error': 'Missing data or s3_key'}), 400
            
        return jsonify(results)
        
    except Exception as e:
        logger.error("Validation request failed", error=str(e))
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

if __name__ == '__main__':
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(level=getattr(logging, log_level))
    
    app.run(host='0.0.0.0', port=8080, debug=False)

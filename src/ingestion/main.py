"""
Data Ingestion Service for Champions League API
Fetches data from RapidAPI UEFA Champions League API and stores in S3 Bronze layer
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

import boto3
import requests
import structlog
from botocore.exceptions import ClientError
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

class ChampionsLeagueIngestionService:
    """Service to ingest Champions League data from RapidAPI UEFA Champions League API"""
    
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'ap-southeast-1'))
        self.bucket_name = os.getenv('S3_BUCKET', 'champions-league-data-lake')
        self.api_base_url = os.getenv('API_BASE_URL', 'https://uefa-champions-league1.p.rapidapi.com')
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY')
        if not self.rapidapi_key:
            raise ValueError("RAPIDAPI_KEY environment variable is required")
        self.rapidapi_host = os.getenv('RAPIDAPI_HOST', 'uefa-champions-league1.p.rapidapi.com')
        self.rate_limit = int(os.getenv('RATE_LIMIT', '100'))
        self.timeout = int(os.getenv('TIMEOUT', '30'))
        self.retry_attempts = int(os.getenv('RETRY_ATTEMPTS', '3'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '1000'))
        
        # Initialize request session with retry strategy
        self.session = requests.Session()
        self.session.headers.update({
            'X-RapidAPI-Key': self.rapidapi_key,
            'X-RapidAPI-Host': self.rapidapi_host,
            'User-Agent': 'ChampionsLeague-DataPipeline/1.0',
            'Accept': 'application/json'
        })
        
    def fetch_data(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Fetch data from RapidAPI UEFA Champions League API with retry logic
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            API response data or None if failed
        """
        url = f"{self.api_base_url}{endpoint}"
        
        for attempt in range(self.retry_attempts):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                data = response.json()
                logger.info(
                    "Successfully fetched data",
                    endpoint=endpoint,
                    status_code=response.status_code,
                    response_size=len(response.content)
                )
                return data
                
            except requests.exceptions.RequestException as e:
                logger.warning(
                    "Request failed",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(
                        "Max retries exceeded",
                        endpoint=endpoint,
                        error=str(e)
                    )
                    return None
                    
    def upload_to_s3(self, data: Dict, key: str) -> bool:
        """
        Upload data to S3 Bronze layer
        
        Args:
            data: Data to upload
            key: S3 key path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add metadata
            enriched_data = {
                'metadata': {
                    'ingestion_timestamp': datetime.utcnow().isoformat(),
                    'source': 'rapidapi_uefa_champions_league',
                    'version': '1.0'
                },
                'data': data
            }
            
            # Convert to JSON string
            json_data = json.dumps(enriched_data, ensure_ascii=False, indent=2)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json_data.encode('utf-8'),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            logger.info(
                "Successfully uploaded to S3",
                bucket=self.bucket_name,
                key=key,
                size=len(json_data)
            )
            return True
            
        except ClientError as e:
            logger.error(
                "Failed to upload to S3",
                bucket=self.bucket_name,
                key=key,
                error=str(e)
            )
            return False
            
    def ingest_standings(self, season: str = "2024") -> bool:
        """Ingest standings data"""
        data = self.fetch_data("/standingsv2", params={"season": season})
        if data:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"bronze/standings/{season}/{timestamp}.json"
            return self.upload_to_s3(data, key)
        return False
        
    def ingest_team_info(self, team_id: str) -> bool:
        """Ingest team info data"""
        data = self.fetch_data("/team/info", params={"teamId": team_id})
        if data:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"bronze/team_info/{team_id}/{timestamp}.json"
            return self.upload_to_s3(data, key)
        return False
        
    def ingest_team_performance(self, team_id: str) -> bool:
        """Ingest team performance data"""
        data = self.fetch_data("/team/perfomance", params={"teamId": team_id})
        if data:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"bronze/team_performance/{team_id}/{timestamp}.json"
            return self.upload_to_s3(data, key)
        return False
        
    def ingest_team_results(self, team_id: str, season: str = "2024") -> bool:
        """Ingest team results data"""
        data = self.fetch_data("/team/results", params={"teamId": team_id, "season": season})
        if data:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"bronze/team_results/{team_id}/{season}/{timestamp}.json"
            return self.upload_to_s3(data, key)
        return False
        
    def ingest_athlete_statistics(self, player_id: str) -> bool:
        """Ingest athlete statistics data"""
        data = self.fetch_data("/athlete/statistic", params={"playerId": player_id})
        if data:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"bronze/athlete_statistics/{player_id}/{timestamp}.json"
            return self.upload_to_s3(data, key)
        return False
        
    def ingest_athlete_bio(self, player_id: str) -> bool:
        """Ingest athlete bio data"""
        data = self.fetch_data("/athlete/bio", params={"playerId": player_id})
        if data:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"bronze/athlete_bio/{player_id}/{timestamp}.json"
            return self.upload_to_s3(data, key)
        return False
        
    def ingest_athlete_season_stats(self, player_id: str, page: str = "1") -> bool:
        """Ingest athlete season stats data"""
        data = self.fetch_data("/athlete/season", params={"playerId": player_id, "page": page})
        if data:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"bronze/athlete_season_stats/{player_id}/{timestamp}.json"
            return self.upload_to_s3(data, key)
        return False
        
    def ingest_athlete_overview(self, player_id: str) -> bool:
        """Ingest athlete overview data"""
        data = self.fetch_data("/athlete/overview", params={"playerId": player_id})
        if data:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"bronze/athlete_overview/{player_id}/{timestamp}.json"
            return self.upload_to_s3(data, key)
        return False
        
    def run_full_ingestion(self, season: str = "2024", team_ids: List[str] = None, player_ids: List[str] = None) -> Dict[str, bool]:
        """Run full ingestion pipeline"""
        results = {}
        
        # Default team IDs (can be expanded)
        if team_ids is None:
            team_ids = ["83", "86", "85", "81"]  # Barcelona, Real Madrid, Bayern Munich, PSG
            
        # Default player IDs (can be expanded)
        if player_ids is None:
            player_ids = ["150225", "164024", "131921"]  # Example player IDs
        
        # Ingest standings
        try:
            results['standings'] = self.ingest_standings(season)
            logger.info("Standings ingestion completed", success=results['standings'])
        except Exception as e:
            results['standings'] = False
            logger.error("Standings ingestion failed", error=str(e))
            
        # Ingest team data
        for team_id in team_ids:
            try:
                results[f'team_info_{team_id}'] = self.ingest_team_info(team_id)
                results[f'team_performance_{team_id}'] = self.ingest_team_performance(team_id)
                results[f'team_results_{team_id}'] = self.ingest_team_results(team_id, season)
                logger.info("Team data ingestion completed", team_id=team_id)
            except Exception as e:
                results[f'team_info_{team_id}'] = False
                results[f'team_performance_{team_id}'] = False
                results[f'team_results_{team_id}'] = False
                logger.error("Team data ingestion failed", team_id=team_id, error=str(e))
                
        # Ingest athlete data
        for player_id in player_ids:
            try:
                results[f'athlete_statistics_{player_id}'] = self.ingest_athlete_statistics(player_id)
                results[f'athlete_bio_{player_id}'] = self.ingest_athlete_bio(player_id)
                results[f'athlete_season_stats_{player_id}'] = self.ingest_athlete_season_stats(player_id)
                results[f'athlete_overview_{player_id}'] = self.ingest_athlete_overview(player_id)
                logger.info("Athlete data ingestion completed", player_id=player_id)
            except Exception as e:
                results[f'athlete_statistics_{player_id}'] = False
                results[f'athlete_bio_{player_id}'] = False
                results[f'athlete_season_stats_{player_id}'] = False
                results[f'athlete_overview_{player_id}'] = False
                logger.error("Athlete data ingestion failed", player_id=player_id, error=str(e))
                
        return results

# Initialize service
ingestion_service = ChampionsLeagueIngestionService()

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'champions-league-ingestion'
    })

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    try:
        # Check S3 connectivity
        ingestion_service.s3_client.head_bucket(Bucket=ingestion_service.bucket_name)
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

@app.route('/ingest', methods=['POST'])
def trigger_ingestion():
    """Trigger data ingestion"""
    try:
        data = request.json or {}
        endpoint = data.get('endpoint', 'all')
        season = data.get('season', '2024')
        team_ids = data.get('team_ids', ["83", "86", "85", "81"])
        player_ids = data.get('player_ids', ["150225", "164024", "131921"])
        
        if endpoint == 'all':
            results = ingestion_service.run_full_ingestion(season, team_ids, player_ids)
        elif endpoint == 'standings':
            results = {'standings': ingestion_service.ingest_standings(season)}
        elif endpoint == 'team_info':
            team_id = data.get('team_id', '83')
            results = {'team_info': ingestion_service.ingest_team_info(team_id)}
        elif endpoint == 'team_performance':
            team_id = data.get('team_id', '83')
            results = {'team_performance': ingestion_service.ingest_team_performance(team_id)}
        elif endpoint == 'team_results':
            team_id = data.get('team_id', '83')
            results = {'team_results': ingestion_service.ingest_team_results(team_id, season)}
        elif endpoint == 'athlete_statistics':
            player_id = data.get('player_id', '150225')
            results = {'athlete_statistics': ingestion_service.ingest_athlete_statistics(player_id)}
        elif endpoint == 'athlete_bio':
            player_id = data.get('player_id', '150225')
            results = {'athlete_bio': ingestion_service.ingest_athlete_bio(player_id)}
        elif endpoint == 'athlete_season_stats':
            player_id = data.get('player_id', '150225')
            page = data.get('page', '1')
            results = {'athlete_season_stats': ingestion_service.ingest_athlete_season_stats(player_id, page)}
        elif endpoint == 'athlete_overview':
            player_id = data.get('player_id', '150225')
            results = {'athlete_overview': ingestion_service.ingest_athlete_overview(player_id)}
        else:
            return jsonify({'error': 'Invalid endpoint'}), 400
            
        return jsonify({
            'status': 'completed',
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Ingestion request failed", error=str(e))
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/endpoints')
def list_endpoints():
    """List available endpoints"""
    return jsonify({
        'endpoints': [
            'all',
            'standings',
            'team_info',
            'team_performance', 
            'team_results',
            'athlete_statistics',
            'athlete_bio',
            'athlete_season_stats',
            'athlete_overview'
        ],
        'parameters': {
            'season': 'Season year (default: 2024)',
            'team_id': 'Team ID (default: 83)',
            'player_id': 'Player ID (default: 150225)',
            'page': 'Page number for athlete season stats (default: 1)',
            'team_ids': 'List of team IDs for full ingestion',
            'player_ids': 'List of player IDs for full ingestion'
        }
    })

if __name__ == '__main__':
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(level=getattr(logging, log_level))
    
    app.run(host='0.0.0.0', port=8080, debug=False)

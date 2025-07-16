"""
Data Transformation Service - Bronze to Silver Layer
Transforms raw Champions League data using PySpark
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import boto3
import structlog
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import *
from pyspark.sql.types import *

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

class BronzeToSilverTransformer:
    """Transforms Bronze layer data to Silver layer"""
    
    def __init__(self):
        self.spark = self._create_spark_session()
        self.s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'ap-southeast-1'))
        self.bucket_name = os.getenv('S3_BUCKET', 'champions-league-data-lake')
        self.input_path = os.getenv('INPUT_PATH', 's3a://champions-league-data-lake/bronze/')
        self.output_path = os.getenv('OUTPUT_PATH', 's3a://champions-league-data-lake/silver/')
        
    def _create_spark_session(self) -> SparkSession:
        """Create Spark session with S3 configuration"""
        spark = SparkSession.builder \
            .appName("ChampionsLeague-BronzeToSilver") \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
            .config("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.DefaultAWSCredentialsProviderChain") \
            .getOrCreate()
            
        spark.sparkContext.setLogLevel("WARN")
        return spark
        
    def transform_standings_data(self) -> None:
        """Transform standings data from Bronze to Silver"""
        try:
            logger.info("Starting standings transformation")
            
            # Read Bronze data
            bronze_df = self.spark.read.json(f"{self.input_path}standings/")
            
            # Extract nested data
            standings_df = bronze_df.select(
                col("metadata.ingestion_timestamp").alias("ingestion_timestamp"),
                col("metadata.source").alias("source"),
                explode(col("data.children")).alias("group")
            ).select(
                col("ingestion_timestamp"),
                col("source"),
                col("group.id").alias("group_id"),
                col("group.name").alias("group_name"),
                col("group.abbreviation").alias("group_abbreviation"),
                explode(col("group.standings.entries")).alias("team_standing")
            ).select(
                col("ingestion_timestamp"),
                col("source"),
                col("group_id"),
                col("group_name"),
                col("group_abbreviation"),
                col("team_standing.team.id").alias("team_id"),
                col("team_standing.team.name").alias("team_name"),
                col("team_standing.team.abbreviation").alias("team_abbreviation"),
                col("team_standing.stats").alias("stats")
            )
            
            # Flatten stats
            stats_df = standings_df.select(
                col("ingestion_timestamp"),
                col("source"),
                col("group_id"),
                col("group_name"),
                col("group_abbreviation"),
                col("team_id"),
                col("team_name"),
                col("team_abbreviation"),
                explode(col("stats")).alias("stat")
            ).select(
                col("ingestion_timestamp"),
                col("source"),
                col("group_id"),
                col("group_name"),
                col("group_abbreviation"),
                col("team_id"),
                col("team_name"),
                col("team_abbreviation"),
                col("stat.name").alias("stat_name"),
                col("stat.value").alias("stat_value")
            )
            
            # Pivot stats to columns
            final_df = stats_df.groupBy(
                "ingestion_timestamp",
                "source",
                "group_id",
                "group_name",
                "group_abbreviation",
                "team_id",
                "team_name",
                "team_abbreviation"
            ).pivot("stat_name").agg(first("stat_value"))
            
            # Add transformation metadata
            final_df = final_df.withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("silver")
            )
            
            # Write to Silver layer
            final_df.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}standings/")
                
            logger.info("Standings transformation completed successfully")
            
        except Exception as e:
            logger.error("Standings transformation failed", error=str(e))
            raise
            
    def transform_teams_data(self) -> None:
        """Transform teams data from Bronze to Silver"""
        try:
            logger.info("Starting teams transformation")
            
            # Read Bronze data
            bronze_df = self.spark.read.json(f"{self.input_path}teams/")
            
            # Extract and flatten team data
            teams_df = bronze_df.select(
                col("metadata.ingestion_timestamp").alias("ingestion_timestamp"),
                col("metadata.source").alias("source"),
                explode(col("data.items")).alias("team")
            ).select(
                col("ingestion_timestamp"),
                col("source"),
                col("team.id").alias("team_id"),
                col("team.uid").alias("team_uid"),
                col("team.slug").alias("team_slug"),
                col("team.location").alias("team_location"),
                col("team.name").alias("team_name"),
                col("team.abbreviation").alias("team_abbreviation"),
                col("team.displayName").alias("team_display_name"),
                col("team.shortDisplayName").alias("team_short_display_name"),
                col("team.color").alias("team_color"),
                col("team.alternateColor").alias("team_alternate_color"),
                col("team.isActive").alias("team_is_active"),
                col("team.logos").alias("team_logos"),
                col("team.links").alias("team_links")
            )
            
            # Add transformation metadata
            teams_df = teams_df.withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("silver")
            )
            
            # Write to Silver layer
            teams_df.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}teams/")
                
            logger.info("Teams transformation completed successfully")
            
        except Exception as e:
            logger.error("Teams transformation failed", error=str(e))
            raise
            
    def transform_athletes_data(self) -> None:
        """Transform athletes data from Bronze to Silver"""
        try:
            logger.info("Starting athletes transformation")
            
            # Read Bronze data
            bronze_df = self.spark.read.json(f"{self.input_path}athletes/")
            
            # Extract and flatten athlete data
            athletes_df = bronze_df.select(
                col("metadata.ingestion_timestamp").alias("ingestion_timestamp"),
                col("metadata.source").alias("source"),
                explode(col("data.items")).alias("athlete")
            ).select(
                col("ingestion_timestamp"),
                col("source"),
                col("athlete.id").alias("athlete_id"),
                col("athlete.uid").alias("athlete_uid"),
                col("athlete.guid").alias("athlete_guid"),
                col("athlete.firstName").alias("athlete_first_name"),
                col("athlete.lastName").alias("athlete_last_name"),
                col("athlete.fullName").alias("athlete_full_name"),
                col("athlete.displayName").alias("athlete_display_name"),
                col("athlete.shortName").alias("athlete_short_name"),
                col("athlete.weight").alias("athlete_weight"),
                col("athlete.height").alias("athlete_height"),
                col("athlete.age").alias("athlete_age"),
                col("athlete.dateOfBirth").alias("athlete_date_of_birth"),
                col("athlete.birthPlace").alias("athlete_birth_place"),
                col("athlete.nationality").alias("athlete_nationality"),
                col("athlete.position").alias("athlete_position"),
                col("athlete.team").alias("athlete_team"),
                col("athlete.jersey").alias("athlete_jersey")
            )
            
            # Add transformation metadata
            athletes_df = athletes_df.withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("silver")
            )
            
            # Write to Silver layer
            athletes_df.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}athletes/")
                
            logger.info("Athletes transformation completed successfully")
            
        except Exception as e:
            logger.error("Athletes transformation failed", error=str(e))
            raise
            
    def transform_events_data(self) -> None:
        """Transform events data from Bronze to Silver"""
        try:
            logger.info("Starting events transformation")
            
            # Read Bronze data
            bronze_df = self.spark.read.json(f"{self.input_path}events/")
            
            # Extract and flatten event data
            events_df = bronze_df.select(
                col("metadata.ingestion_timestamp").alias("ingestion_timestamp"),
                col("metadata.source").alias("source"),
                explode(col("data.events")).alias("event")
            ).select(
                col("ingestion_timestamp"),
                col("source"),
                col("event.id").alias("event_id"),
                col("event.uid").alias("event_uid"),
                col("event.date").alias("event_date"),
                col("event.name").alias("event_name"),
                col("event.shortName").alias("event_short_name"),
                col("event.status").alias("event_status"),
                col("event.competitions").alias("event_competitions"),
                col("event.season").alias("event_season"),
                col("event.timeValid").alias("event_time_valid"),
                col("event.links").alias("event_links")
            )
            
            # Add transformation metadata
            events_df = events_df.withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("silver")
            )
            
            # Write to Silver layer
            events_df.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}events/")
                
            logger.info("Events transformation completed successfully")
            
        except Exception as e:
            logger.error("Events transformation failed", error=str(e))
            raise
            
    def run_all_transformations(self) -> Dict[str, bool]:
        """Run all Bronze to Silver transformations"""
        results = {}
        
        transformations = [
            ("standings", self.transform_standings_data),
            ("teams", self.transform_teams_data),
            ("athletes", self.transform_athletes_data),
            ("events", self.transform_events_data)
        ]
        
        for name, transform_func in transformations:
            try:
                transform_func()
                results[name] = True
                logger.info("Transformation completed", transformation=name)
            except Exception as e:
                results[name] = False
                logger.error("Transformation failed", transformation=name, error=str(e))
                
        return results
        
    def cleanup(self):
        """Clean up Spark session"""
        if self.spark:
            self.spark.stop()

def main():
    """Main execution function"""
    transformer = BronzeToSilverTransformer()
    
    try:
        results = transformer.run_all_transformations()
        
        # Log summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        logger.info(
            "Bronze to Silver transformation completed",
            successful=successful,
            total=total,
            results=results
        )
        
        # Exit with appropriate code
        if successful == total:
            exit(0)
        else:
            exit(1)
            
    except Exception as e:
        logger.error("Transformation job failed", error=str(e))
        exit(1)
        
    finally:
        transformer.cleanup()

if __name__ == "__main__":
    main()

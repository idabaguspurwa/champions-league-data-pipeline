"""
Data Transformation Service - Silver to Gold Layer
Creates business-ready datasets for analytics and reporting
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
from pyspark.sql.window import Window

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

class SilverToGoldTransformer:
    """Transforms Silver layer data to Gold layer business-ready datasets"""
    
    def __init__(self):
        self.spark = self._create_spark_session()
        self.s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'ap-southeast-1'))
        self.bucket_name = os.getenv('S3_BUCKET', 'champions-league-data-lake')
        self.input_path = os.getenv('INPUT_PATH', 's3a://champions-league-data-lake/silver/')
        self.output_path = os.getenv('OUTPUT_PATH', 's3a://champions-league-data-lake/gold/')
        
    def _create_spark_session(self) -> SparkSession:
        """Create Spark session with S3 configuration"""
        spark = SparkSession.builder \
            .appName("ChampionsLeague-SilverToGold") \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
            .config("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.DefaultAWSCredentialsProviderChain") \
            .getOrCreate()
            
        spark.sparkContext.setLogLevel("WARN")
        return spark
        
    def create_team_performance_summary(self) -> None:
        """Create team performance summary from standings data"""
        try:
            logger.info("Creating team performance summary")
            
            # Read Silver standings data
            standings_df = self.spark.read.parquet(f"{self.input_path}standings/")
            
            # Create team performance metrics
            performance_df = standings_df.select(
                col("group_id"),
                col("group_name"),
                col("team_id"),
                col("team_name"),
                col("team_abbreviation"),
                col("gamesPlayed").cast("int").alias("games_played"),
                col("wins").cast("int").alias("wins"),
                col("losses").cast("int").alias("losses"),
                col("ties").cast("int").alias("ties"),
                col("points").cast("int").alias("points"),
                col("pointsPerGame").cast("double").alias("points_per_game"),
                col("goalsFor").cast("int").alias("goals_for"),
                col("goalsAgainst").cast("int").alias("goals_against"),
                col("goalDifferential").cast("int").alias("goal_differential"),
                col("rank").cast("int").alias("group_rank")
            ).filter(
                col("games_played").isNotNull() & 
                col("points").isNotNull()
            )
            
            # Calculate additional metrics
            performance_df = performance_df.withColumn(
                "win_percentage",
                when(col("games_played") > 0, 
                     col("wins") / col("games_played") * 100
                ).otherwise(0)
            ).withColumn(
                "goals_per_game",
                when(col("games_played") > 0,
                     col("goals_for") / col("games_played")
                ).otherwise(0)
            ).withColumn(
                "goals_conceded_per_game",
                when(col("games_played") > 0,
                     col("goals_against") / col("games_played")
                ).otherwise(0)
            ).withColumn(
                "performance_rating",
                col("points_per_game") * 10 + col("goal_differential")
            )
            
            # Add ranking within overall competition
            window_spec = Window.orderBy(col("points").desc(), col("goal_differential").desc())
            performance_df = performance_df.withColumn(
                "overall_rank",
                row_number().over(window_spec)
            )
            
            # Add transformation metadata
            performance_df = performance_df.withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("gold")
            ).withColumn(
                "dataset_name",
                lit("team_performance_summary")
            )
            
            # Write to Gold layer
            performance_df.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}team_performance_summary/")
                
            logger.info("Team performance summary created successfully")
            
        except Exception as e:
            logger.error("Team performance summary creation failed", error=str(e))
            raise
            
    def create_player_analytics(self) -> None:
        """Create player analytics from athletes data"""
        try:
            logger.info("Creating player analytics")
            
            # Read Silver athletes data
            athletes_df = self.spark.read.parquet(f"{self.input_path}athletes/")
            
            # Clean and process athlete data
            player_df = athletes_df.select(
                col("athlete_id"),
                col("athlete_full_name").alias("player_name"),
                col("athlete_display_name").alias("player_display_name"),
                col("athlete_age").cast("int").alias("age"),
                col("athlete_weight").cast("double").alias("weight_kg"),
                col("athlete_height").cast("double").alias("height_cm"),
                col("athlete_birth_place").alias("birth_place"),
                col("athlete_nationality").alias("nationality"),
                col("athlete_position").alias("position"),
                col("athlete_team").alias("team_info"),
                col("athlete_jersey").alias("jersey_number")
            ).filter(
                col("player_name").isNotNull() &
                col("age").isNotNull()
            )
            
            # Extract team information
            player_df = player_df.withColumn(
                "team_id",
                col("team_info.id")
            ).withColumn(
                "team_name",
                col("team_info.name")
            ).withColumn(
                "team_abbreviation",
                col("team_info.abbreviation")
            )
            
            # Calculate age groups
            player_df = player_df.withColumn(
                "age_group",
                when(col("age") <= 21, "Youth (≤21)")
                .when(col("age") <= 25, "Young (22-25)")
                .when(col("age") <= 29, "Prime (26-29)")
                .when(col("age") <= 33, "Experienced (30-33)")
                .otherwise("Veteran (34+)")
            )
            
            # Add BMI calculation
            player_df = player_df.withColumn(
                "bmi",
                when(
                    col("weight_kg").isNotNull() & col("height_cm").isNotNull(),
                    col("weight_kg") / (col("height_cm") / 100) / (col("height_cm") / 100)
                ).otherwise(null())
            )
            
            # Add transformation metadata
            player_df = player_df.withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("gold")
            ).withColumn(
                "dataset_name",
                lit("player_analytics")
            )
            
            # Write to Gold layer
            player_df.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}player_analytics/")
                
            logger.info("Player analytics created successfully")
            
        except Exception as e:
            logger.error("Player analytics creation failed", error=str(e))
            raise
            
    def create_team_roster_summary(self) -> None:
        """Create team roster summary from athletes data"""
        try:
            logger.info("Creating team roster summary")
            
            # Read Silver athletes data
            athletes_df = self.spark.read.parquet(f"{self.input_path}athletes/")
            
            # Aggregate by team
            roster_summary = athletes_df.groupBy(
                col("athlete_team.id").alias("team_id"),
                col("athlete_team.name").alias("team_name"),
                col("athlete_team.abbreviation").alias("team_abbreviation")
            ).agg(
                count("*").alias("total_players"),
                avg("athlete_age").alias("avg_age"),
                min("athlete_age").alias("min_age"),
                max("athlete_age").alias("max_age"),
                avg("athlete_weight").alias("avg_weight"),
                avg("athlete_height").alias("avg_height"),
                collect_set("athlete_nationality").alias("nationalities"),
                collect_set("athlete_position").alias("positions")
            ).filter(
                col("team_id").isNotNull()
            )
            
            # Calculate additional metrics
            roster_summary = roster_summary.withColumn(
                "nationality_count",
                size(col("nationalities"))
            ).withColumn(
                "position_count",
                size(col("positions"))
            ).withColumn(
                "age_diversity",
                col("max_age") - col("min_age")
            )
            
            # Add transformation metadata
            roster_summary = roster_summary.withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("gold")
            ).withColumn(
                "dataset_name",
                lit("team_roster_summary")
            )
            
            # Write to Gold layer
            roster_summary.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}team_roster_summary/")
                
            logger.info("Team roster summary created successfully")
            
        except Exception as e:
            logger.error("Team roster summary creation failed", error=str(e))
            raise
            
    def create_competition_overview(self) -> None:
        """Create competition overview from multiple sources"""
        try:
            logger.info("Creating competition overview")
            
            # Read Silver data
            standings_df = self.spark.read.parquet(f"{self.input_path}standings/")
            teams_df = self.spark.read.parquet(f"{self.input_path}teams/")
            
            # Create competition metrics
            competition_stats = standings_df.agg(
                countDistinct("team_id").alias("total_teams"),
                countDistinct("group_id").alias("total_groups"),
                sum(col("gamesPlayed").cast("int")).alias("total_games_played"),
                sum(col("goalsFor").cast("int")).alias("total_goals_scored"),
                avg(col("goalsFor").cast("int")).alias("avg_goals_per_team"),
                max(col("points").cast("int")).alias("max_points"),
                min(col("points").cast("int")).alias("min_points")
            )
            
            # Calculate goals per game
            competition_stats = competition_stats.withColumn(
                "goals_per_game",
                when(col("total_games_played") > 0,
                     col("total_goals_scored") / col("total_games_played")
                ).otherwise(0)
            )
            
            # Add metadata
            competition_stats = competition_stats.withColumn(
                "competition_name",
                lit("UEFA Champions League")
            ).withColumn(
                "season",
                lit("2024-25")
            ).withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("gold")
            ).withColumn(
                "dataset_name",
                lit("competition_overview")
            )
            
            # Write to Gold layer
            competition_stats.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}competition_overview/")
                
            logger.info("Competition overview created successfully")
            
        except Exception as e:
            logger.error("Competition overview creation failed", error=str(e))
            raise
            
    def create_group_analysis(self) -> None:
        """Create group-level analysis"""
        try:
            logger.info("Creating group analysis")
            
            # Read Silver standings data
            standings_df = self.spark.read.parquet(f"{self.input_path}standings/")
            
            # Group-level statistics
            group_stats = standings_df.groupBy(
                col("group_id"),
                col("group_name")
            ).agg(
                count("*").alias("teams_in_group"),
                sum(col("gamesPlayed").cast("int")).alias("total_games_played"),
                sum(col("goalsFor").cast("int")).alias("total_goals_scored"),
                avg(col("points").cast("int")).alias("avg_points_per_team"),
                max(col("points").cast("int")).alias("group_leader_points"),
                min(col("points").cast("int")).alias("group_lowest_points"),
                avg(col("goalDifferential").cast("int")).alias("avg_goal_differential"),
                max(col("goalDifferential").cast("int")).alias("best_goal_differential"),
                min(col("goalDifferential").cast("int")).alias("worst_goal_differential")
            )
            
            # Calculate competitiveness metrics
            group_stats = group_stats.withColumn(
                "points_spread",
                col("group_leader_points") - col("group_lowest_points")
            ).withColumn(
                "competitiveness_score",
                when(col("points_spread") > 0,
                     100 / col("points_spread")
                ).otherwise(100)
            ).withColumn(
                "goals_per_game",
                when(col("total_games_played") > 0,
                     col("total_goals_scored") / col("total_games_played")
                ).otherwise(0)
            )
            
            # Add ranking for most competitive groups
            window_spec = Window.orderBy(col("competitiveness_score").desc())
            group_stats = group_stats.withColumn(
                "competitiveness_rank",
                row_number().over(window_spec)
            )
            
            # Add transformation metadata
            group_stats = group_stats.withColumn(
                "transformation_timestamp",
                lit(datetime.utcnow().isoformat())
            ).withColumn(
                "data_layer",
                lit("gold")
            ).withColumn(
                "dataset_name",
                lit("group_analysis")
            )
            
            # Write to Gold layer
            group_stats.coalesce(1).write \
                .mode("overwrite") \
                .option("compression", "snappy") \
                .parquet(f"{self.output_path}group_analysis/")
                
            logger.info("Group analysis created successfully")
            
        except Exception as e:
            logger.error("Group analysis creation failed", error=str(e))
            raise
            
    def run_all_transformations(self) -> Dict[str, bool]:
        """Run all Silver to Gold transformations"""
        results = {}
        
        transformations = [
            ("team_performance_summary", self.create_team_performance_summary),
            ("player_analytics", self.create_player_analytics),
            ("team_roster_summary", self.create_team_roster_summary),
            ("competition_overview", self.create_competition_overview),
            ("group_analysis", self.create_group_analysis)
        ]
        
        for name, transform_func in transformations:
            try:
                transform_func()
                results[name] = True
                logger.info("Gold dataset created", dataset=name)
            except Exception as e:
                results[name] = False
                logger.error("Gold dataset creation failed", dataset=name, error=str(e))
                
        return results
        
    def cleanup(self):
        """Clean up Spark session"""
        if self.spark:
            self.spark.stop()

def main():
    """Main execution function"""
    transformer = SilverToGoldTransformer()
    
    try:
        results = transformer.run_all_transformations()
        
        # Log summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        logger.info(
            "Silver to Gold transformation completed",
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

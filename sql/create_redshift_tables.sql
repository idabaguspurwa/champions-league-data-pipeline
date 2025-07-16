-- Champions League Data Warehouse Schema
-- Redshift table creation script

-- Create schema
CREATE SCHEMA IF NOT EXISTS champions_league;

-- Set search path
SET search_path = champions_league;

-- Drop tables if they exist (for development)
DROP TABLE IF EXISTS dim_teams CASCADE;
DROP TABLE IF EXISTS dim_players CASCADE;
DROP TABLE IF EXISTS dim_groups CASCADE;
DROP TABLE IF EXISTS dim_dates CASCADE;
DROP TABLE IF EXISTS fact_team_performance CASCADE;
DROP TABLE IF EXISTS fact_player_stats CASCADE;
DROP TABLE IF EXISTS fact_match_results CASCADE;

-- Dimension Tables

-- Teams dimension
CREATE TABLE dim_teams (
    team_id VARCHAR(20) PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL,
    team_abbreviation VARCHAR(10),
    team_display_name VARCHAR(100),
    team_location VARCHAR(100),
    team_color VARCHAR(10),
    team_alternate_color VARCHAR(10),
    team_is_active BOOLEAN DEFAULT TRUE,
    team_logos TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Players dimension
CREATE TABLE dim_players (
    player_id VARCHAR(20) PRIMARY KEY,
    player_name VARCHAR(100) NOT NULL,
    player_display_name VARCHAR(100),
    age INTEGER,
    weight_kg DECIMAL(5,2),
    height_cm DECIMAL(5,2),
    birth_place VARCHAR(100),
    nationality VARCHAR(50),
    position VARCHAR(50),
    jersey_number INTEGER,
    team_id VARCHAR(20),
    age_group VARCHAR(20),
    bmi DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES dim_teams(team_id)
);

-- Groups dimension
CREATE TABLE dim_groups (
    group_id VARCHAR(20) PRIMARY KEY,
    group_name VARCHAR(100) NOT NULL,
    group_abbreviation VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Date dimension
CREATE TABLE dim_dates (
    date_id DATE PRIMARY KEY,
    year INTEGER,
    month INTEGER,
    day INTEGER,
    quarter INTEGER,
    week INTEGER,
    day_of_week INTEGER,
    day_name VARCHAR(20),
    month_name VARCHAR(20),
    is_weekend BOOLEAN,
    season VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fact Tables

-- Team performance fact table
CREATE TABLE fact_team_performance (
    performance_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    team_id VARCHAR(20) NOT NULL,
    group_id VARCHAR(20) NOT NULL,
    date_id DATE NOT NULL,
    games_played INTEGER,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    points INTEGER,
    points_per_game DECIMAL(5,2),
    goals_for INTEGER,
    goals_against INTEGER,
    goal_differential INTEGER,
    group_rank INTEGER,
    overall_rank INTEGER,
    win_percentage DECIMAL(5,2),
    goals_per_game DECIMAL(5,2),
    goals_conceded_per_game DECIMAL(5,2),
    performance_rating DECIMAL(8,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES dim_teams(team_id),
    FOREIGN KEY (group_id) REFERENCES dim_groups(group_id),
    FOREIGN KEY (date_id) REFERENCES dim_dates(date_id)
);

-- Player statistics fact table
CREATE TABLE fact_player_stats (
    stat_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    player_id VARCHAR(20) NOT NULL,
    team_id VARCHAR(20) NOT NULL,
    date_id DATE NOT NULL,
    games_played INTEGER,
    goals INTEGER,
    assists INTEGER,
    yellow_cards INTEGER,
    red_cards INTEGER,
    minutes_played INTEGER,
    shots INTEGER,
    shots_on_target INTEGER,
    pass_completion_rate DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES dim_players(player_id),
    FOREIGN KEY (team_id) REFERENCES dim_teams(team_id),
    FOREIGN KEY (date_id) REFERENCES dim_dates(date_id)
);

-- Match results fact table
CREATE TABLE fact_match_results (
    match_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    event_id VARCHAR(20) NOT NULL,
    home_team_id VARCHAR(20) NOT NULL,
    away_team_id VARCHAR(20) NOT NULL,
    group_id VARCHAR(20) NOT NULL,
    match_date DATE NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    match_status VARCHAR(20),
    attendance INTEGER,
    venue VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (home_team_id) REFERENCES dim_teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES dim_teams(team_id),
    FOREIGN KEY (group_id) REFERENCES dim_groups(group_id),
    FOREIGN KEY (match_date) REFERENCES dim_dates(date_id)
);

-- Indexes for performance optimization
CREATE INDEX idx_team_performance_team_date ON fact_team_performance(team_id, date_id);
CREATE INDEX idx_team_performance_group ON fact_team_performance(group_id);
CREATE INDEX idx_player_stats_player_date ON fact_player_stats(player_id, date_id);
CREATE INDEX idx_player_stats_team ON fact_player_stats(team_id);
CREATE INDEX idx_match_results_date ON fact_match_results(match_date);
CREATE INDEX idx_match_results_teams ON fact_match_results(home_team_id, away_team_id);

-- Views for common queries

-- Team performance summary view
CREATE VIEW v_team_performance_summary AS
SELECT 
    t.team_name,
    t.team_abbreviation,
    g.group_name,
    tp.games_played,
    tp.wins,
    tp.losses,
    tp.ties,
    tp.points,
    tp.goal_differential,
    tp.group_rank,
    tp.overall_rank,
    tp.win_percentage,
    tp.performance_rating
FROM fact_team_performance tp
JOIN dim_teams t ON tp.team_id = t.team_id
JOIN dim_groups g ON tp.group_id = g.group_id
WHERE tp.date_id = (SELECT MAX(date_id) FROM fact_team_performance);

-- Top scorers view
CREATE VIEW v_top_scorers AS
SELECT 
    p.player_name,
    p.position,
    t.team_name,
    SUM(ps.goals) as total_goals,
    SUM(ps.assists) as total_assists,
    SUM(ps.games_played) as total_games,
    CASE 
        WHEN SUM(ps.games_played) > 0 
        THEN ROUND(SUM(ps.goals)::DECIMAL / SUM(ps.games_played), 2)
        ELSE 0 
    END as goals_per_game
FROM fact_player_stats ps
JOIN dim_players p ON ps.player_id = p.player_id
JOIN dim_teams t ON ps.team_id = t.team_id
GROUP BY p.player_name, p.position, t.team_name
ORDER BY total_goals DESC, total_assists DESC;

-- Group standings view
CREATE VIEW v_group_standings AS
SELECT 
    g.group_name,
    t.team_name,
    tp.points,
    tp.games_played,
    tp.wins,
    tp.losses,
    tp.ties,
    tp.goals_for,
    tp.goals_against,
    tp.goal_differential,
    tp.group_rank
FROM fact_team_performance tp
JOIN dim_teams t ON tp.team_id = t.team_id
JOIN dim_groups g ON tp.group_id = g.group_id
WHERE tp.date_id = (SELECT MAX(date_id) FROM fact_team_performance)
ORDER BY g.group_name, tp.group_rank;

-- Recent matches view
CREATE VIEW v_recent_matches AS
SELECT 
    mr.match_date,
    ht.team_name as home_team,
    at.team_name as away_team,
    mr.home_score,
    mr.away_score,
    mr.match_status,
    g.group_name,
    mr.venue
FROM fact_match_results mr
JOIN dim_teams ht ON mr.home_team_id = ht.team_id
JOIN dim_teams at ON mr.away_team_id = at.team_id
JOIN dim_groups g ON mr.group_id = g.group_id
ORDER BY mr.match_date DESC
LIMIT 20;

-- Data quality monitoring queries

-- Check for missing data
CREATE VIEW v_data_quality_check AS
SELECT 
    'Teams' as table_name,
    COUNT(*) as record_count,
    COUNT(CASE WHEN team_name IS NULL THEN 1 END) as null_names,
    COUNT(CASE WHEN team_id IS NULL THEN 1 END) as null_ids
FROM dim_teams
UNION ALL
SELECT 
    'Players' as table_name,
    COUNT(*) as record_count,
    COUNT(CASE WHEN player_name IS NULL THEN 1 END) as null_names,
    COUNT(CASE WHEN player_id IS NULL THEN 1 END) as null_ids
FROM dim_players
UNION ALL
SELECT 
    'Team Performance' as table_name,
    COUNT(*) as record_count,
    COUNT(CASE WHEN points IS NULL THEN 1 END) as null_points,
    COUNT(CASE WHEN team_id IS NULL THEN 1 END) as null_team_ids
FROM fact_team_performance;

-- Performance monitoring
CREATE VIEW v_performance_metrics AS
SELECT 
    'fact_team_performance' as table_name,
    COUNT(*) as row_count,
    MIN(created_at) as earliest_record,
    MAX(created_at) as latest_record,
    COUNT(DISTINCT team_id) as unique_teams,
    COUNT(DISTINCT date_id) as unique_dates
FROM fact_team_performance
UNION ALL
SELECT 
    'fact_player_stats' as table_name,
    COUNT(*) as row_count,
    MIN(created_at) as earliest_record,
    MAX(created_at) as latest_record,
    COUNT(DISTINCT player_id) as unique_players,
    COUNT(DISTINCT date_id) as unique_dates
FROM fact_player_stats;

-- Grant permissions (adjust as needed)
GRANT SELECT ON ALL TABLES IN SCHEMA champions_league TO tableau_user;
GRANT SELECT ON ALL TABLES IN SCHEMA champions_league TO readonly_user;

-- Comments for documentation
COMMENT ON TABLE dim_teams IS 'Dimension table containing team information';
COMMENT ON TABLE dim_players IS 'Dimension table containing player information';
COMMENT ON TABLE fact_team_performance IS 'Fact table containing team performance metrics';
COMMENT ON TABLE fact_player_stats IS 'Fact table containing player statistics';
COMMENT ON VIEW v_team_performance_summary IS 'Latest team performance summary';
COMMENT ON VIEW v_top_scorers IS 'Top goal scorers across all teams';
COMMENT ON VIEW v_group_standings IS 'Current group standings';

-- Maintenance procedures
-- Vacuum and analyze tables for performance
VACUUM FULL dim_teams;
VACUUM FULL dim_players;
VACUUM FULL fact_team_performance;
VACUUM FULL fact_player_stats;

ANALYZE dim_teams;
ANALYZE dim_players;
ANALYZE fact_team_performance;
ANALYZE fact_player_stats;

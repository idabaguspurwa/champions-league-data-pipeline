# Champions League Analytics - Tableau Dashboard Configuration

This document outlines the Tableau dashboard configuration for Champions League analytics.

## Data Sources

### Primary Data Source: Amazon Redshift
- **Connection Type**: Amazon Redshift
- **Server**: {redshift_cluster_endpoint}
- **Database**: champions_league_db
- **Schema**: champions_league
- **Authentication**: Username/Password (stored in AWS Secrets Manager)

### Backup Data Source: S3 (CSV Files)
- **Connection Type**: Amazon S3
- **Bucket**: champions-league-data-lake
- **Path**: /exports/tableau/
- **File Format**: CSV
- **Refresh**: Daily

## Dashboard Structure

### Dashboard 1: Competition Overview
**Purpose**: High-level tournament overview and key metrics

**Visualizations**:
1. **KPI Cards** (Top Row)
   - Total Teams: `COUNT(DISTINCT [Team Name])`
   - Total Groups: `COUNT(DISTINCT [Group Name])`
   - Total Goals: `SUM([Goals For])`
   - Average Goals per Game: `SUM([Goals For]) / SUM([Games Played])`

2. **Group Standings Table** (Left Side)
   - Columns: Group, Team, Points, Wins, Losses, Ties, Goal Diff
   - Sorting: Group Name, then Points (descending)
   - Color coding: Green for qualification positions

3. **Goals Distribution Chart** (Right Side)
   - Chart Type: Horizontal Bar Chart
   - Dimension: Team Name
   - Measure: Goals For
   - Sort: Descending by Goals For
   - Color: Team Colors (if available)

4. **Performance Trend** (Bottom)
   - Chart Type: Line Chart
   - X-axis: Date
   - Y-axis: Points
   - Color: Team Name
   - Filter: Select specific teams

### Dashboard 2: Team Performance Analysis
**Purpose**: Detailed team performance metrics and comparisons

**Visualizations**:
1. **Team Selector** (Top)
   - Parameter: Team Selection
   - Control: Dropdown

2. **Performance Radar Chart** (Left)
   - Metrics: Win %, Goals per Game, Goals Conceded, Points per Game
   - Comparison: Selected team vs. Average
   - Chart Type: Radar/Spider Chart

3. **Head-to-Head Matrix** (Right)
   - Chart Type: Matrix/Heatmap
   - Rows: Home Team
   - Columns: Away Team
   - Values: Match Results (Win/Draw/Loss)

4. **Team Statistics Table** (Bottom)
   - Columns: Team, Games, W-D-L, Points, GF, GA, GD, Form
   - Sorting: Points (descending)
   - Conditional formatting: Colors based on performance

### Dashboard 3: Player Analytics
**Purpose**: Individual player performance and statistics

**Visualizations**:
1. **Top Performers** (Top Row)
   - Top Goalscorers: Bar chart
   - Top Assisters: Bar chart
   - Most Appearances: Bar chart

2. **Player Details** (Left)
   - Player selector dropdown
   - Player information card
   - Performance metrics (Goals, Assists, Games)

3. **Age Distribution** (Right)
   - Chart Type: Histogram
   - Dimension: Age Groups
   - Measure: Player Count
   - Color: Position

4. **Team Composition** (Bottom)
   - Chart Type: Treemap
   - Dimension: Team, Position
   - Measure: Player Count
   - Color: Team Colors

### Dashboard 4: Match Analysis
**Purpose**: Match results and fixture analysis

**Visualizations**:
1. **Fixture Calendar** (Top)
   - Chart Type: Calendar Heatmap
   - Date: Match Date
   - Color: Match Outcome
   - Tooltip: Team names and scores

2. **Match Results Timeline** (Middle)
   - Chart Type: Gantt Chart
   - Date: Match Date
   - Teams: Home vs Away
   - Color: Result (Win/Draw/Loss)

3. **Venue Analysis** (Bottom Left)
   - Chart Type: Map
   - Location: Venue
   - Size: Number of matches
   - Color: Average attendance

4. **Score Distribution** (Bottom Right)
   - Chart Type: Scatter Plot
   - X-axis: Home Score
   - Y-axis: Away Score
   - Color: Match Outcome

## Calculated Fields

### Key Performance Indicators
```sql
-- Win Percentage
[Wins] / [Games Played] * 100

-- Goals Per Game
[Goals For] / [Games Played]

-- Goals Conceded Per Game
[Goals Against] / [Games Played]

-- Points Per Game
[Points] / [Games Played]

-- Performance Rating
[Points Per Game] * 10 + [Goal Differential]
```

### Advanced Metrics
```sql
-- Form (Last 5 Games)
-- This requires a more complex calculation based on recent matches

-- Expected Points (based on goal difference)
IF [Goal Differential] > 0 THEN 3
ELSEIF [Goal Differential] = 0 THEN 1
ELSE 0
END

-- Qualification Status
IF [Group Rank] <= 2 THEN "Qualified"
ELSEIF [Group Rank] = 3 THEN "Europa League"
ELSE "Eliminated"
END
```

## Filters and Parameters

### Global Filters
- **Season**: 2024-25 (default)
- **Group**: All groups (multi-select)
- **Team**: All teams (multi-select)
- **Date Range**: Last 30 days (default)

### Dashboard-Specific Parameters
- **Team Comparison**: For performance analysis
- **Player Position**: For player analytics
- **Match Type**: Group Stage, Knockout (future)

## Data Refresh Schedule

### Automated Refresh
- **Frequency**: Every 6 hours
- **Method**: Tableau Server/Online scheduled refresh
- **Data Source**: Amazon Redshift (primary)
- **Fallback**: S3 CSV files

### Manual Refresh
- **Trigger**: After major data updates
- **Method**: Tableau Desktop or Server
- **Validation**: Data quality checks

## Performance Optimization

### Data Extraction
- **Strategy**: Live connection to Redshift for real-time data
- **Backup**: Extracted data for offline analysis
- **Aggregation**: Pre-aggregated tables for faster queries

### Query Optimization
- **Indexes**: Ensure proper indexing on Redshift tables
- **Partitioning**: Date-based partitioning for large tables
- **Materialized Views**: For complex calculations

## Security and Access

### Row-Level Security
- **Not implemented** (public tournament data)
- **Future consideration**: Team-specific access if needed

### User Permissions
- **Public Dashboard**: Read-only access
- **Admin Users**: Full edit permissions
- **Data Analysts**: Edit permissions for specific dashboards

## Deployment Instructions

### 1. Setup Data Connection
1. Open Tableau Desktop
2. Connect to Amazon Redshift
3. Enter connection details from Terraform outputs
4. Test connection and verify data

### 2. Create Calculated Fields
1. Create all calculated fields listed above
2. Test calculations with sample data
3. Document field descriptions

### 3. Build Visualizations
1. Follow the dashboard structure outlined above
2. Apply consistent formatting and colors
3. Add appropriate filters and parameters

### 4. Dashboard Configuration
1. Arrange visualizations according to layout
2. Configure dashboard actions (filters, highlights)
3. Add navigation between dashboards

### 5. Publishing
1. Publish to Tableau Server/Online
2. Configure refresh schedule
3. Set up user permissions
4. Test end-to-end functionality

## Troubleshooting

### Common Issues
1. **Connection Timeout**: Check Redshift cluster status and security groups
2. **Data Not Refreshing**: Verify scheduled refresh settings
3. **Performance Issues**: Check query performance and add indexes
4. **Missing Data**: Verify data pipeline execution

### Support Contacts
- **Data Engineering**: Monitor Airflow DAG execution
- **Infrastructure**: Check AWS resources and permissions
- **Tableau Admin**: Dashboard configuration and publishing

## Future Enhancements

### Planned Features
1. **Real-time Updates**: Live data streaming for match events
2. **Advanced Analytics**: Machine learning predictions
3. **Mobile Optimization**: Responsive dashboard design
4. **API Integration**: Direct connection to Champions League API

### Technical Improvements
1. **Performance Optimization**: Query caching and materialized views
2. **Data Quality**: Automated data validation and alerts
3. **Security**: Enhanced access controls and audit logging
4. **Scalability**: Support for multiple tournaments and seasons

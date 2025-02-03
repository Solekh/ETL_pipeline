# Transfermarkt Top Scorers Data Pipeline

## Project Overview
This project automates the extraction of top goal scorers from Transfermarkt.com and stores the data in a PostgreSQL database using Apache Airflow. The pipeline:
1. Scrapes the top goal scorers from major European leagues.
2. Stores the data in a PostgreSQL database.
3. Runs daily using Apache Airflow for automation.

## Tech Stack
- **Apache Airflow**: Manages the ETL pipeline.
- **Docker & Docker Compose**: Containerization and orchestration.
- **PostgreSQL**: Stores the extracted goal scorer data.
- **Python & BeautifulSoup**: Scrapes Transfermarkt.com.
- **Requests & Pandas**: Handles API calls and data processing.

## Installation & Setup
### Prerequisites
- Install **Docker & Docker Compose**.
- Ensure **Airflow** is properly set up.

### Steps
1. Clone this repository:
   ```sh
   git clone <repo_url>
   cd <project_directory>
   ```
2. Start Docker containers:
   ```sh
   docker-compose up -d
   ```
3. Access Airflow UI:
   - Open [http://localhost:8080](http://localhost:8080)
   - Enable and trigger the `store_top_scorers` DAG.

## How It Works
### DAG Workflow
1. **Fetch Top Scorers**: Scrapes Transfermarkt.com for the top goal scorers.
2. **Create Database Table**: Ensures a PostgreSQL table (`top_scorers`) exists.
3. **Store Data**: Inserts the extracted data into the database.

### Database Schema (`top_scorers` Table)
| Column       | Type    | Description                 |
|-------------|--------|-----------------------------|
| id          | SERIAL | Primary key                 |
| league      | TEXT   | League name                 |
| player      | TEXT   | Player's name               |
| club        | TEXT   | Club name                   |
| goals       | INT    | Number of goals scored      |
| appearances | INT    | Number of matches played    |

## Usage Instructions
### Running the Pipeline
- The DAG is scheduled to run **daily**.
- To trigger manually:
  1. Go to the **Airflow UI**.
  2. Enable the `store_top_scorers` DAG.
  3. Click **Trigger DAG**.

### Querying Data
To retrieve stored data, connect to the PostgreSQL database:
```sh
psql -h localhost -U postgres -d football_stats
```
Run SQL queries:
```sql
SELECT * FROM top_scorers ORDER BY goals DESC;
```

## Future Improvements
- Add more leagues and seasons.
- Improve anti-bot mechanisms.
- Store historical data for analysis.


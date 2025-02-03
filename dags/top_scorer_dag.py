from datetime import datetime, timedelta
import time
import random
import requests
import pandas as pd
import csv
import os
from bs4 import BeautifulSoup
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.log.logging_mixin import LoggingMixin

# Anti-blocking: Rotating user-agent headers
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
]

LEAGUE_URLS = {
    "Premier League": "https://www.transfermarkt.com/premier-league/torschuetzenliste/wettbewerb/GB1",
    "La Liga": "https://www.transfermarkt.com/laliga/torschuetzenliste/wettbewerb/ES1",
    "Bundesliga": "https://www.transfermarkt.com/bundesliga/torschuetzenliste/wettbewerb/L1",
    "Serie A": "https://www.transfermarkt.com/serie-a/torschuetzenliste/wettbewerb/IT1",
    "Ligue 1": "https://www.transfermarkt.com/ligue-1/torschuetzenliste/wettbewerb/FR1",
}

CSV_FILE_PATH = "/tmp/top_scorers.csv"  # Path to save the CSV file


def get_random_user_agent():
    return random.choice(USER_AGENTS)


def fetch_top_scorers():
    """Fetch top scorers from Transfermarkt and save to a CSV file."""
    session = requests.Session()
    all_scorers = []

    for league, url in LEAGUE_URLS.items():
        headers = {"User-Agent": get_random_user_agent()}

        try:
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            table = soup.find("table", class_="items")
            if not table:
                LoggingMixin().log.warning(f"Table not found for {league}")
                continue

            rows = table.find_all("tr", class_=["odd", "even"])  # Extract both odd and even rows

            for row in rows[:10]:  # Fetch top 10 scorers per league
                cols = row.find_all("td")
                if len(cols) > 5:  # Ensure there are enough columns

                    # Extract player name and position separately
                    player_info = cols[1].text.strip()
                    player_parts = player_info.split("\n")
                    player_name = player_parts[0].strip()
                    player_position = player_parts[1].strip() if len(player_parts) > 1 else "Unknown"

                    # Extract club name
                    club = cols[3].img["alt"] if cols[3].img else "Unknown"

                    # Extract and clean goals & appearances
                    goals = cols[4].text.strip()
                    appearances = cols[5].text.strip()

                    try:
                        goals = int(goals)
                    except ValueError:
                        goals = 0

                    try:
                        appearances = int(appearances)
                    except ValueError:
                        appearances = 0

                    # Store extracted data
                    all_scorers.append([league, player_name, player_position, club, goals, appearances])

            time.sleep(random.uniform(3, 7))  # Random delay for anti-blocking

        except requests.exceptions.RequestException as e:
            LoggingMixin().log.error(f"Failed to fetch data for {league}: {e}")

    if not all_scorers:
        raise ValueError("No data fetched from Transfermarkt")

    # Save data to CSV file
    with open(CSV_FILE_PATH, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["League", "Player", "Position", "Club", "Goals", "Appearances"])  # Headers
        writer.writerows(all_scorers)

    LoggingMixin().log.info(f"Data successfully saved to {CSV_FILE_PATH}")


def insert_scorers_into_postgres():
    """Reads the CSV file and inserts the data into PostgreSQL."""
    postgres_hook = PostgresHook(postgres_conn_id='football_stats')

    if not os.path.exists(CSV_FILE_PATH):
        raise FileNotFoundError(f"CSV file {CSV_FILE_PATH} not found.")

    # Read CSV file
    with open(CSV_FILE_PATH, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)  # Skip header row

        insert_query = """
        INSERT INTO top_scorers (league, player, position, club, goals, appearances)
        VALUES (%s, %s, %s, %s, %s, %s)
        """

        for row in reader:
            try:
                postgres_hook.run(insert_query, parameters=row)
            except Exception as e:
                LoggingMixin().log.error(f"Failed to insert player {row[1]}: {e}")

    LoggingMixin().log.info("Data successfully inserted into PostgreSQL.")


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 6, 20),
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'store_top_scorers',
    default_args=default_args,
    description='Fetch top goal scorers from Transfermarkt and store in Postgres',
    schedule_interval=timedelta(days=1),
    catchup=False,
)

fetch_top_scorers_task = PythonOperator(
    task_id='fetch_top_scorers',
    python_callable=fetch_top_scorers,
    dag=dag,
)

create_table_task = PostgresOperator(
    task_id='create_table',
    postgres_conn_id='football_stats',
    sql="""
    CREATE TABLE IF NOT EXISTS top_scorers (
        id SERIAL PRIMARY KEY,
        league TEXT NOT NULL,
        player TEXT NOT NULL,
        position TEXT,
        club TEXT,
        goals INTEGER,
        appearances INTEGER
    );
    """,
    dag=dag,
)

insert_scorers_task = PythonOperator(
    task_id='insert_scorers',
    python_callable=insert_scorers_into_postgres,
    dag=dag,
)

fetch_top_scorers_task >> create_table_task >> insert_scorers_task

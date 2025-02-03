from datetime import datetime, timedelta
import time
import random
import requests
import csv
import os
from bs4 import BeautifulSoup
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.log.logging_mixin import LoggingMixin

user_agents_list = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
]

leagues_links = {
    "Premier League": "https://www.transfermarkt.com/premier-league/torschuetzenliste/wettbewerb/GB1",
    "La Liga": "https://www.transfermarkt.com/laliga/torschuetzenliste/wettbewerb/ES1",
    "Bundesliga": "https://www.transfermarkt.com/bundesliga/torschuetzenliste/wettbewerb/L1",
    "Serie A": "https://www.transfermarkt.com/serie-a/torschuetzenliste/wettbewerb/IT1",
    "Ligue 1": "https://www.transfermarkt.com/ligue-1/torschuetzenliste/wettbewerb/FR1",
}

file_path = "/tmp/scorers.csv"


def pick_user_agent():
    return random.choice(user_agents_list)


def scrape_scorers():
    session = requests.Session()
    players_data = []

    for league, url in leagues_links.items():
        headers = {"User-Agent": pick_user_agent()}
        try:
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            table = soup.find("table", class_="items")
            if not table:
                LoggingMixin().log.warning(f"No table for {league}")
                continue

            rows = table.find_all("tr", class_=["odd", "even"])
            for row in rows[:10]:
                cols = row.find_all("td")
                if len(cols) > 5:
                    player_info = cols[1].text.strip().split("\n")
                    name = player_info[0].strip()
                    position = player_info[1].strip() if len(player_info) > 1 else "Unknown"
                    club = cols[3].img["alt"] if cols[3].img else "Unknown"
                    goals = cols[4].text.strip()
                    matches = cols[5].text.strip()

                    try:
                        goals = int(goals)
                    except ValueError:
                        goals = 0

                    try:
                        matches = int(matches)
                    except ValueError:
                        matches = 0

                    players_data.append([league, name, position, club, goals, matches])
            time.sleep(random.uniform(3, 7))
        except requests.exceptions.RequestException as e:
            LoggingMixin().log.error(f"Error fetching {league}: {e}")

    if not players_data:
        raise ValueError("No data scraped")

    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["League", "Player", "Position", "Club", "Goals", "Matches"])
        writer.writerows(players_data)

    LoggingMixin().log.info(f"Saved data to {file_path}")


def save_to_db():
    db = PostgresHook(postgres_conn_id='football_db')
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} missing")

    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        insert_query = """
        INSERT INTO top_scorers (league, player, position, club, goals, appearances)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        for row in reader:
            try:
                db.run(insert_query, parameters=row)
            except Exception as e:
                LoggingMixin().log.error(f"Failed to insert {row[1]}: {e}")
    LoggingMixin().log.info("Data added to DB")


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 6, 20),
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'goal_scorers_pipeline',
    default_args=default_args,
    description='Scrape and store football top scorers',
    schedule_interval=timedelta(days=1),
    catchup=False,
)

scrape_task = PythonOperator(
    task_id='scrape_scorers',
    python_callable=scrape_scorers,
    dag=dag,
)

create_table = PostgresOperator(
    task_id='create_scorers_table',
    postgres_conn_id='football_db',
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

save_task = PythonOperator(
    task_id='save_scorers',
    python_callable=save_to_db,
    dag=dag,
)

scrape_task >> create_table >> save_task

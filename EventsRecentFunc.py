from mssql_python import connect
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import geopandas as gpd
from shapely.geometry import Point, Polygon, shape
import json
import sqlalchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


load_dotenv()

TOKEN_URL = os.getenv("TOKEN_URL")
EVENTS_RECENT_BASE_URL = os.getenv("EVENTS_RECENT_BASE_URL")
API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
DRIVER = os.getenv("DRIVER")
SERVER = os.getenv("SERVER")
INITIAL_CATALOG = os.getenv("INITIAL_CATALOG")
USER_ID = os.getenv("USER_ID")
PASSWORD = os.getenv("PASSWORD")



connection_string = (
    f"DRIVER={DRIVER};"
    f"SERVER={SERVER};"
    f"DATABASE={INITIAL_CATALOG};"
    "Persist Security Info=False;"
    f"UID={USER_ID};"
    f"PWD={PASSWORD};"
    "MultipleActiveResultSets=False;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)
def get_access_token(token_url: str,
                     basic_auth_key: str,
                     grant_type: str = "client_credentials") -> str:

    headers = {
        "Authorization": f"Basic {basic_auth_key}"
    }

    data = {
        "grant_type": grant_type
    }

    response = requests.post(token_url, headers=headers, data=data)
    response.raise_for_status()

    return response.json()["access_token"]



def get_events_recent(events_recent_url: str,
                            access_token: str) -> pd.DataFrame:

    events_recent_headers = {
    "Accept": "application/vnd.mds+json;version=2.0",
    "Authorization": f"Bearer {access_token}"
    }

    events_recent_response = requests.get(events_recent_url, headers = events_recent_headers)
    events_recent_json = events_recent_response.json()
    events_recent_df = pd.json_normalize(events_recent_json["events"])

    events_recent_df['timestamp'] = pd.to_datetime(events_recent_df['timestamp'], unit = 'ms', utc = True)
    #events_recent_df['event_types'] = events_recent_df['event_types'].apply(lambda x: x[0])

    # Due to the string convertion of .strftime(), which is the foramt we want because it's ledgable and easy to understand
    events_recent_df['timestamp'] = events_recent_df['timestamp'].dt.strftime(
    "%d/%m/%Y %H:%M:%S")

    events_recent_df['timestamp'] = pd.to_datetime(
    events_recent_df['timestamp'], format="%d/%m/%Y %H:%M:%S")

    def extract_first(x):
        if isinstance(x, list):
            return x[0] if len(x) > 0 else None
        return x 

    events_recent_df['event_types'] = events_recent_df['event_types'].apply(extract_first)
    events_recent_df['trip_ids'] = events_recent_df['trip_ids'].apply(extract_first)

    #Reset index of dataframe
    events_recent_df = events_recent_df.reset_index(drop = True)

    #Changing names to meet SQL table creation requirements
    events_recent_df = events_recent_df.rename(columns = {'location.lat':'lat', 'location.lng':'lon'})


    events_recent_df = events_recent_df.where(
        pd.notnull(events_recent_df), None
    )

    print(events_recent_df.dtypes)


    return events_recent_df

end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
start_time = end_time + timedelta(hours=-1)

start_time = int(start_time.timestamp() *1000)
end_time = int(end_time.timestamp() * 1000)

EVENTS_RECENT_URL = (
    f"{EVENTS_RECENT_BASE_URL}"
    f"?start_time={start_time}&end_time={end_time}"
)

connect = mssql-python.connect(connection_string)
with connect as connect:
    connect.execute(""" DROP TABLE events_recent""")

def run_events_recent():

    token = get_access_token(TOKEN_URL, API_KEY)

    events_recent_df = get_events_recent(
    events_recent_url= EVENTS_RECENT_URL,
    access_token=token)

    
    connect = mssql-python.connect(connection_string)
    
    cursor = connect.cursor()

    with connect as connect:
        cursor.execute("""

        IF EXISTS (
            SELECT 1 
            FROM sys.tables
            WHERE name = 'events_recent'
        )
        BEGIN
            DROP TABLE events_recent
        END

        IF NOT EXISTS (
            SELECT 1 
            FROM sys.tables
            WHERE name = 'events_recent'
        )                                         
        BEGIN              
            CREATE TABLE events_recent (
                battery_percent NUMERIC,       
                device_id VARCHAR(50),
                event_id VARCHAR(50),
                event_types VARCHAR(100),
                provider_id VARCHAR(50),
                timestamp DATETIME,
                vehicle_state VARCHAR(100),
                lat NUMERIC,
                lon NUMERIC,
                trip_ids VARCHAR(50),
                PRIMARY KEY (event_id, timestamp))
        END     
    """)

        connect.commit()

    connect = mssql-python.connect(connection_string)
    
    cursor = connect.cursor()

    insert_sql = """
    INSERT INTO events_recent (
        battery_percent,
        device_id,
        event_id,
        event_types,
        provider_id,
        timestamp,
        vehicle_state,
        lat,
        lon,
        trip_ids
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    data = list(events_recent_df.itertuples(index=False, name=None))

    cursor.executemany(insert_sql, data)

    connect.commit()
        
        

    print("SQL - Completed")


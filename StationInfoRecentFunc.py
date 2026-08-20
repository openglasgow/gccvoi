### Station info - Function 

from mssql_python import connect
import os
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = os.getenv("TOKEN_URL")
STATION_INFO_URL = os.getenv("STATION_INFO_URL")
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


def get_station_information_recent(station_info_url: str,
                            access_token: str) -> pd.DataFrame:


    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(station_info_url, headers=headers)
    response.raise_for_status()

    station_json = response.json()

    df = pd.json_normalize(station_json["data"]["stations"])
    df['timestamp'] = datetime.now()
    pd.to_datetime(df['timestamp'])

    df['timestamp'] = datetime.now()

    def round_5(dt):
        base_dt = dt.replace(second = 0, microsecond = 0)
        minute_reminder = dt.minute % 5
        total_seconds = (minute_reminder * 60) + dt.second

        if total_seconds >= 150:
            return base_dt + timedelta(minutes=(5 - minute_reminder))
        else:
            return base_dt - timedelta(minutes = minute_reminder)
        
    df['rounded_timestamp'] = df['timestamp'].apply(round_5)



    # Extract station name from multilingual field
    if "name" in df.columns:
        df["station_name"] = df["name"].apply(
            lambda x: x[0]["text"] if x else None
        )
        df.drop(columns=["name", "station_area.coordinates", "station_area.type"], inplace=True)

    return df

#connect = mssql-python.connect(connection_string)
#with connect as connect:
    #connect.execute(""" DROP TABLE station_information""")

def run_station_information_recent():
    token = get_access_token(TOKEN_URL, API_KEY)

    station_info_df = get_station_information_recent(
    station_info_url=STATION_INFO_URL,
    access_token=token)
    
    print('Data Queried')

    connect = mssql-python.connect(connection_string)

    cursor = connect.cursor()

    with connect as connect:
        cursor.execute("""

        IF EXISTS (
            SELECT 1 
            FROM sys.tables
            WHERE name = 'station_information_recent'
        )
        BEGIN
            DROP TABLE station_information_recent
        END

        IF NOT EXISTS (
            SELECT 1
            FROM sys.tables
            WHERE name = 'station_information_recent')    

        BEGIN              
            CREATE TABLE station_information_recent (
                capacity INT,
                is_virtual_station BIT,
                lat NUMERIC,
                lon NUMERIC,
                station_id VARCHAR(50),
                timestamp DATETIME, 
                rounded_timestamp DATETIME,             
                station_name VARCHAR(300),       
                PRIMARY KEY (station_id))
        END     
    """)

        connect.commit()     
    
    connect = mssql-python.connect(connection_string)
    
    cursor = connect.cursor()

    insert_sql = """
    INSERT INTO station_information_recent (
        capacity,
        is_virtual_station,
        lat,
        lon,
        station_id,
        timestamp,
        rounded_timestamp,
        station_name
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    data = list(station_info_df.itertuples(index=False, name=None))

    cursor.executemany(insert_sql, data)

    connect.commit()



    print('Database created')

run_station_information_recent()


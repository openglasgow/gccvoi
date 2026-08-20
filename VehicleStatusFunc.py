from mssql_python import connect
import os
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from dotenv import load_dotenv


load_dotenv()

TOKEN_URL = os.getenv("TOKEN_URL")
VEHICLE_STATUS_URL = os.getenv("VEHICLE_STATUS_URL")
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


def get_vehicle_status(vehicle_status_url: str,
                            access_token: str) -> pd.DataFrame:


    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(vehicle_status_url, headers=headers)
    response.raise_for_status()

    vehicle_json = response.json()

    df = pd.json_normalize(vehicle_json["data"]["vehicles"])
    df.drop(columns=["rental_uris.android", "rental_uris.ios"], inplace=True)
    
    df['last_reported'] = pd.to_datetime(df["last_reported"])
    
    df['timestamp'] = datetime.now()

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    def round_5(dt):
        base_dt = dt.replace(second = 0, microsecond = 0)
        minute_reminder = dt.minute % 5
        total_seconds = (minute_reminder * 60) + dt.second

        if total_seconds >= 150:
            return base_dt + timedelta(minutes=(5 - minute_reminder))
        else:
            return base_dt - timedelta(minutes = minute_reminder)
        
    df['rounded_timestamp'] = df['timestamp'].apply(round_5)

    df = df.where(
        pd.notnull(df), None
    )

    print(df.dtypes)
    print(df.isna().sum())

    

    return df



#connect = connect(connection_string)
#with connect as connect:
    #connect.execute(""" DROP TABLE vehicle_status""")

def run_vehicle_status():
    token = get_access_token(TOKEN_URL, API_KEY)

    vehicle_status_df = get_vehicle_status(
    vehicle_status_url=VEHICLE_STATUS_URL,
    access_token=token
)
    
    
    #vehicle_status_df.to_csv('vehicle_status.csv')
    
    connect = connect(connection_string)

    cursor = connect.cursor()

    with connect as connect:
        cursor.execute("""

        IF NOT EXISTS (
            SELECT 1 
            FROM sys.tables
            WHERE name = 'vehicle_status'
        )                                         
        BEGIN              
            CREATE TABLE vehicle_status (
            current_fuel_percent FLOAT,
            current_range_meters INT,
            is_disabled BIT,
            is_reserved BIT,
            last_reported DATETIME,
            lat FLOAT,
            lon FLOAT,
            station_id VARCHAR(50) NULL,
            vehicle_id VARCHAR(50),
            vehicle_type_id VARCHAR(50),
            timestamp DATETIME,
            rounded_timestamp DATETIME,           
            PRIMARY KEY (vehicle_id, rounded_timestamp),
            CONSTRAINT fk_station_info_to_vehicle
                         FOREIGN KEY (station_id, rounded_timestamp)
                         REFERENCES station_information (station_id, rounded_timestamp))
        END     
    """)

    connect.commit()     
    
    connect = connect(connection_string)
    
    cursor = connect.cursor()

    insert_sql = """
    INSERT INTO vehicle_status (
        current_fuel_percent,
        current_range_meters,
        is_disabled,
        is_reserved,
        last_reported,
        lat,
        lon,
        station_id,
        vehicle_id,
        vehicle_type_id,
        timestamp,
        rounded_timestamp
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    data = list(vehicle_status_df.itertuples(index=False, name=None))

    cursor.executemany(insert_sql, data)

    connect.commit()

print("Database Updated")

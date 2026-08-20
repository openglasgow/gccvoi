import mssql-python
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
STATION_INFO_URL = os.getenv("STATION_INFO_URL")
EVENTS_HISTORICAL_URL = os.getenv("EVENTS_HISTORICAL_URL")
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

def stations_areas(station_info_url: str,
                            access_token: str) -> pd.DataFrame:


    station_info_headers = {
        "Authorization": f"Bearer {access_token}"
    }

    station_info_response = requests.get(station_info_url, headers=station_info_headers)
    station_info_response.raise_for_status()

    station_json = station_info_response.json()

    df = pd.json_normalize(station_json["data"]["stations"])
    df['timestamp'] = datetime.now()

    # Extract station name from multilingual field
    if "name" in df.columns:
        df["station_name"] = df["name"].apply(
            lambda x: x[0]["text"] if x else None
        )

    print("station_info - Compiled") 

    return df

def get_events_historical_daily(events_historical_url: str, access_token: str) -> pd.DataFrame:

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    overall_start = today - timedelta(days=1) # Making it start at the beginning of the previous day
    overall_end = today - timedelta(hours=1)
    
    events_historical_data = []

    current_start = overall_start

    while current_start <= overall_end: # The main loop to process every month

        # First day of next month
        if current_start.month == 12: ## Since december is the end of the year, below we had to create the start of a new year
            next_month = datetime(
                current_start.year + 1,
                1,
                1,
                current_start.hour
            )
        else:
            next_month = datetime(   ## This just runs the rest of the months after january
                current_start.year,
                current_start.month + 1,
                1,
                current_start.hour
            )

        current_end = min(    # basically calculates the current month junk in hours, use min to make sure its doing it in order, example 1,2,3,4 istead of 1,4,2,3 but for time
            next_month - timedelta(hours=1),
            overall_end
        )

        print(
            f"Processing {current_start:%Y-%m} "
            f"({current_start} -> {current_end})"
        )

        # Refresh token for each of the months

        access_token = get_access_token(TOKEN_URL, API_KEY)


        events_historical_headers = {
            "Accept": "application/vnd.mds+json;version=2.0",
            "Authorization": f"Bearer {access_token}"
        }

        # Processing every hour in month
        
        event_date = current_start

        while event_date <= current_end:

            event_time = event_date.strftime("%Y-%m-%dT%H")

            try:

                response = requests.get(
                    events_historical_url,
                    headers=events_historical_headers,
                    params={"event_time": event_time},
                    timeout=30
                )

                response.raise_for_status()

                events_historical_data.append(
                    response.json()
                )

                print(f"✓ {event_time}")

            except Exception as e:
                print(f"✗ {event_time}: {e}")

            event_date += timedelta(hours=1)

        print(f"Completed {current_start:%Y-%m}")

        current_start = next_month

    print(
        f"Finished. Retrieved "
        f"{len(events_historical_data)} responses."
    )
    print(f"Completed {current_start:%Y-%m}")
    print(f"Next month will start at {next_month}")

    events_historical_df = pd.DataFrame(events_historical_data)

    #Creating a row for each individual event from lists (JSONs)
    events_historical_df = events_historical_df.explode("events")
    events_historical_df = pd.json_normalize(events_historical_df["events"])

    events_historical_df['timestamp'] = (
        pd.to_datetime(events_historical_df['timestamp'], unit='ms', utc=True)
        .dt.tz_convert('Europe/London')
        .dt.tz_localize(None))

    #Cleaning timestamp (from unix to standard format) and extracting event types from list format (string)
    #events_historical_df['timestamp'] = pd.to_datetime(events_historical_df['timestamp'], unit = 'ms', utc = True)

    # Once again reformating the datetime for azure sql
    events_historical_df['timestamp'] = events_historical_df['timestamp'].dt.strftime(
    "%d/%m/%Y %H:%M:%S")
    
    #Extracting first element of event type list (format varies in source data)
    def first_item(x):
        if isinstance(x, list) and x:
            return x[0]
        return None
    events_historical_df['event_types'] = events_historical_df['event_types'].apply(first_item)
    
    #Extracting trip IDs from lists - require function
    def extract_first(x):
        if isinstance(x, list):
            return x[0] if len(x) > 0 else None
        return x 

    events_historical_df["trip_ids"] = events_historical_df["trip_ids"].apply(extract_first)

    #Reset index of dataframe
    events_historical_df = events_historical_df.reset_index(drop = True)

    #Changing names to meet SQL table creation requirements
    events_historical_df = events_historical_df.rename(columns = {'location.lat':'lat', 'location.lng':'lon'})

    return events_historical_df


def run_events_historical_daily():

    token = get_access_token(TOKEN_URL, API_KEY)

    station_info_df = stations_areas(
    station_info_url = STATION_INFO_URL,
    access_token = token)

    events_historical_df = get_events_historical_daily(
    events_historical_url= EVENTS_HISTORICAL_URL,
    access_token = token)
    
    print("daily function started")
    ###Geospatial Cleaning - Events Historical
    #Adding stations to events (if applicable)

    #Combining event co-ordinate columns to give points in geopandas format
    events_historical_df['geometry'] = events_historical_df.apply(
        lambda row: Point(row['lon'], row['lat']), axis = 1
    )

    events_historical_gdf = gpd.GeoDataFrame(
        events_historical_df,
        geometry = 'geometry',
        crs = 'EPSG:4326' #Best co-ordinate reference system for Great Britain
    )

    ##Translating station polygon co-ordinates to geopandas polygon objects - multiple possible types
    station_info_df['geometry'] = station_info_df['station_area.coordinates'].apply(lambda coords: Polygon(coords[0][0]))

    station_info_gdf = gpd.GeoDataFrame(
        station_info_df,
        geometry = 'geometry',
        crs = 'EPSG:4326'
    )

    print(station_info_gdf.geometry.is_valid.value_counts())
    print(station_info_gdf.geometry.geom_type.value_counts())

    #Using a spatial join to assign stations to events
    events_historical_joined =gpd.sjoin(
        events_historical_gdf,
        station_info_gdf[['station_name','geometry']],
        how = 'left', #Left join looking for where events happen within a station
        predicate = 'within'
    )

    events_historical_joined = events_historical_joined.sort_index().groupby(level=0).first()
    
    events_historical_df = events_historical_df.join(
    events_historical_joined[['station_name']],
    how='left')

    events_historical_df = events_historical_df.drop(columns = 'geometry')
    
    # Makes all NA's as nulls for Azure SQL
    events_historical_df = events_historical_df.where(
        pd.notnull(events_historical_df), None
    )

    print(events_historical_df.dtypes)

    #print(events_historical_df)
    #print(events_historical_joined.index.is_unique)

    #connect = mssql-python.connect(connection_string)
    #with connect as connect:
        #connect.execute(""" DROP TABLE events_historical""")

    #events_historical_df.to_csv("events_historical_daily.csv", index= False)     

    connect = mssql-python.connect(connection_string)
    
    cursor = connect.cursor()

    with connect as connect:
        cursor.execute("""

        IF NOT EXISTS (
            SELECT 1 
            FROM sys.tables
            WHERE name = 'events_historical'
        )                                         
        BEGIN              
            CREATE TABLE events_historical (
                battery_percent INT,
                device_id VARCHAR(50),
                event_id VARCHAR(50),
                event_types VARCHAR(100),
                provider_id VARCHAR(50),
                timestamp DATETIME,
                trip_ids VARCHAR(50),
                vehicle_state VARCHAR(100),
                lat FLOAT,
                lon FLOAT,
                station_name VARCHAR(300),
                PRIMARY KEY (event_id, timestamp))
        END     
    """)

        connect.commit()

    connect = mssql-python.connect(connection_string)
    
    #cursor = connect.cursor()

    insert_sql = """
    INSERT INTO events_historical (
        battery_percent,
        device_id,
        event_id,
        event_types,
        provider_id,
        timestamp,
        trip_ids,
        vehicle_state,
        lat,
        lon,
        station_name 
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    data = list(events_historical_df.itertuples(index=False, name=None))

    cursor.executemany(insert_sql, data)

    connect.commit()
       
    print("SQL - Completed")


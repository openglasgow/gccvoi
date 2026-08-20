import os
from mssql_python import connect
import requests
import pandas as pd
from datetime import datetime, timedelta
import sqlalchemy
from sqlalchemy import create_engine, text
import geopandas as gpd
from shapely.geometry import Point, Polygon, shape
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = os.getenv("TOKEN_URL")
STATION_INFO_URL = os.getenv("STATION_INFO_URL")
TRIPS_URL = os.getenv("TRIPS_URL")
GEOFENCE_URL = os.getenv("GEOFENCE_URL")
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

def geofence_areas(geofence_url: str,
                            access_token: str) -> pd.DataFrame:


    geofence_headers = {
        "Authorization": f"Bearer {access_token}"
    }

    geofence_response = requests.get(geofence_url, headers=geofence_headers)
    geofence_response.raise_for_status()

    geofence_json = geofence_response.json()

    df = pd.json_normalize(geofence_json["data"]["geofencing_zones"]['features'])

    df['geofence_name'] = df['properties.name'].apply(
    lambda x: x[0]['text'] if x else None)

    expand = df['properties.rules'].str[0].apply(pd.Series)

    df = pd.concat([df, expand], axis = 1)

    df = df.drop(columns= ["properties.rules", "properties.name",])

    df['timestamp'] = datetime.now()

    df['geofence_name'] = df["geofence_name"].str.replace(
    "Glasgow - ", "", regex=False)

    print("Queries - Compiled") 

    return df

def get_trips_daily(trips_url: str,
                            access_token: str) -> pd.DataFrame:

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    overall_start = today - timedelta(days=1) # Making it start at the beginning of the previous day
    overall_end = today - timedelta(hours=1)

    trips_data = []

    current_start = overall_start

    while current_start <= overall_end: # The main loop to process every month

        # First day of next month
        if current_start.month == 12: ## Since december is the end of the year, below we had to create the start of a new year
            next_month = datetime(
                current_start.year + 1,
                1,
                1,
                0
            )
        else:
            next_month = datetime(   ## This just runs the rest of the months after january
                current_start.year,
                current_start.month + 1,
                1,
                0
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


        trips_headers = {
            "Accept": "application/vnd.mds+json;version=2.0",
            "Authorization": f"Bearer {access_token}"
        }

        # Processing every hour in month
        
        event_date = current_start

        while event_date <= current_end:

            event_time = event_date.strftime("%Y-%m-%dT%H")

            try:

                response = requests.get(
                    trips_url,
                    headers=trips_headers,
                    params={"end_time": event_time},
                    timeout=30
                )

                response.raise_for_status()

                trips_data.append(
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
        f"{len(trips_data)} responses."
    )
    print(f"Completed {current_start:%Y-%m}")
    print(f"Next month will start at {next_month}")
    print(len(trips_data))

    trips_df = pd.DataFrame(trips_data)

    #Creating a row for each individual event from lists (JSONs)
    trips_df = trips_df.explode("trips")
    trips_df = pd.json_normalize(trips_df["trips"])

    trips_df['start_time'] = (
    pd.to_datetime(trips_df['start_time'], unit='ms', utc=True)
      .dt.tz_convert('Europe/London')
      .dt.tz_localize(None))

    trips_df['end_time'] = (
    pd.to_datetime(trips_df['end_time'], unit='ms', utc=True)
      .dt.tz_convert('Europe/London')
      .dt.tz_localize(None))

# A Mini function to extract the trip types from a list in which its stored in.
    def extract_first(x):
        if isinstance(x, list):
            return x[0] if len(x) > 0 else None
        return x 
    trips_df["trip_type"] = trips_df["trip_type"].apply(extract_first)
    trips_df = trips_df.drop(columns= ['accessibility_attributes']) # cloumn filled with empty lists
    
    trips_df = trips_df.reset_index(drop = True)
    #Changing names to meet SQL table creation requirements
    trips_df = trips_df.rename(columns = {'end_location.lat':'end_lat', 'end_location.lng':'end_lon', 
                                          'start_location.lat' : 'start_lat', 'start_location.lng':'start_lon'})
  
    return trips_df

## Code to drop table if needed
#connect = connect(connection_string)
#with connect as connect:
    #connect.execute(""" DROP TABLE trips""")

def run_trips_daily():

    token = get_access_token(TOKEN_URL, API_KEY)

    station_info_df = stations_areas(
    station_info_url = STATION_INFO_URL,
    access_token = token)

    geofence_df = geofence_areas(
    geofence_url = GEOFENCE_URL,
    access_token = token)

    trips_df = get_trips_daily(
    trips_url=TRIPS_URL,
    access_token=token)

    ###Geospatial Cleaning - Trips(Start station)
    #Adding stations to events (if applicable)

    #Combining event co-ordinate columns to give points in geopandas format
    trips_df['geometry'] = trips_df.apply(
        lambda row: Point(row['start_lon'], row['start_lat']), axis = 1
    )

    trips_gdf = gpd.GeoDataFrame(
        trips_df,
        geometry = 'geometry',
        crs = 'EPSG:4326' #Best co-ordinate reference system for Great Britain
    )

    trips_gdf = trips_gdf.to_crs("EPSG:27700")

    def build_station_geometry(row):
        geojson = {
        "type": row["station_area.type"],
        "coordinates": row["station_area.coordinates"]
        }
        return shape(geojson)

    station_info_df["geometry"] = station_info_df.apply(build_station_geometry, axis=1)
    
    station_info_gdf = gpd.GeoDataFrame(
        station_info_df,
        geometry = 'geometry',
        crs = 'EPSG:4326'
    )

    station_info_gdf = station_info_gdf.to_crs("EPSG:27700")
    station_info_gdf["geometry"] = station_info_gdf.geometry.buffer(25)
    
    #Using a spatial join to assign stations to trips(start)
    trips_joined =gpd.sjoin(
        trips_gdf,
        station_info_gdf[['station_name', 'station_id', 'geometry']],
        how = 'left', #Left join looking for where events happen within a station
        predicate = 'intersects'
    )
    
    trips_joined = trips_joined.sort_index().groupby(level=0).first()
    
    trips_df = trips_df.join(
    trips_joined[['station_name', 'station_id']],
    how='left')

    # Renaming the station name column for it to specifically relate to start to differentiated between start and end
    trips_df = trips_df.rename(columns = {'station_name': 'start_station_name',
                                          'station_id' : 'start_station_id'})
    trips_df = trips_df.drop(columns = 'geometry')

    ###Geospatial Cleaning - Trips(end station)
    #Adding stations to events (if applicable)

    #Combining event co-ordinate columns to give points in geopandas format
    trips_df['geometry'] = trips_df.apply(
        lambda row: Point(row['end_lon'], row['end_lat']), axis = 1
    )

    trips_gdf = gpd.GeoDataFrame(
        trips_df,
        geometry = 'geometry',
        crs = 'EPSG:4326' #Best co-ordinate reference system for Great Britain
    )

    trips_gdf = trips_gdf.to_crs("EPSG:27700")

    #Using a spatial join to assign stations to trips(end)
    trips_joined =gpd.sjoin(
        trips_gdf,
        station_info_gdf[['station_name','station_id', 'geometry']],
        how = 'left', #Left join looking for where events happen within a station
        predicate = 'intersects'
    )
    
    trips_joined = trips_joined.sort_index().groupby(level=0).first()
    
    trips_df = trips_df.join(
    trips_joined[['station_name', 'station_id']],
    how='left')
     
    trips_df = trips_df.rename(columns = {'station_name': 'end_station_name',
                                          'station_id' : 'end_station_id'}) 
    trips_df = trips_df.drop(columns = 'geometry')

    trips_df['geometry'] = trips_df.apply(
        lambda row: Point(row['start_lon'], row['start_lat']), axis = 1
    )

    trips_gdf = gpd.GeoDataFrame(
        trips_df,
        geometry = 'geometry',
        crs = 'EPSG:4326' #Best co-ordinate reference system for Great Britain
    )

    trips_gdf = trips_gdf.to_crs("EPSG:27700")

    def build_geofence_geometry(row):
        geojson = {
        "type": row["geometry.type"],
        "coordinates": row["geometry.coordinates"]
        }
        return shape(geojson)

    geofence_df["geometry"] = geofence_df.apply(build_geofence_geometry, axis=1)
    
    geofence_gdf = gpd.GeoDataFrame(
        geofence_df,
        geometry = 'geometry',
        crs = 'EPSG:4326'
    )

    geofence_gdf = geofence_gdf.to_crs("EPSG:27700")
    geofence_gdf["geometry"] = geofence_gdf.geometry.buffer(10)
    
    #Using a spatial join to assign stations to trips(start)
    trips_joined =gpd.sjoin(
        trips_gdf,
        geofence_gdf[['geofence_name','geometry']],
        how = 'left', #Left join looking for where events happen within a station
        predicate = 'intersects'
    )
    
    trips_joined = trips_joined.sort_index().groupby(level=0).first()
    
    trips_df = trips_df.join(
    trips_joined[['geofence_name']],
    how='left')

    # Renaming the station name column for it to specifically relate to start to differentiated between start and end
    trips_df = trips_df.rename(columns = {'geofence_name': 'start_geofence_name'})
    trips_df = trips_df.drop(columns = 'geometry')

    ###Geospatial Cleaning - Trips(end station)
    #Adding stations to events (if applicable)

    #Combining event co-ordinate columns to give points in geopandas format
    trips_df['geometry'] = trips_df.apply(
        lambda row: Point(row['end_lon'], row['end_lat']), axis = 1
    )

    trips_gdf = gpd.GeoDataFrame(
        trips_df,
        geometry = 'geometry',
        crs = 'EPSG:4326' #Best co-ordinate reference system for Great Britain
    )

    trips_gdf = trips_gdf.to_crs("EPSG:27700")

    #Using a spatial join to assign stations to trips(end)
    trips_joined =gpd.sjoin(
        trips_gdf,
        geofence_gdf[['geofence_name','geometry']],
        how = 'left', #Left join looking for where events happen within a station
        predicate = 'intersects'
    )
    
    trips_joined = trips_joined.sort_index().groupby(level=0).first()
    
    trips_df = trips_df.join(
    trips_joined[['geofence_name']],
    how='left')
     
    trips_df = trips_df.rename(columns = {'geofence_name': 'end_geofence_name'}) 
    trips_df = trips_df.drop(columns = 'geometry')

    trips_df = trips_df.where(
            pd.notnull(trips_df), None
        )

    trips_df["distance"] = trips_df["distance"].fillna("0")

    print(trips_df.dtypes)
    print(trips_df[["distance", "end_lat", "end_lon", "start_lat", "start_lon"]].isna().sum())

    #trips_df.to_csv("trips.csv", index= False)

    print('Data Queried - beginning SQL')

    connect = connect(connection_string)
        
    cursor = connect.cursor()
    
    with connect as connect:
        cursor.execute("""
    
        IF NOT EXISTS (
            SELECT 1 
            FROM sys.tables
            WHERE name = 'trips'
            )                                         
            BEGIN              
                CREATE TABLE trips (
                    device_id VARCHAR(50),
                    distance FLOAT,
                    duration INT,
                    end_time DATETIME,
                    provider_id VARCHAR(50),
                    start_time DATETIME,
                    trip_id VARCHAR(50),
                    trip_type VARCHAR(100),
                    end_lat FLOAT,
                    end_lon FLOAT,
                    start_lat FLOAT,
                    start_lon FLOAT,
                    start_station_name VARCHAR(100),
                    start_station_id VARCHAR(50),
                    end_station_name VARCHAR(100),
                    end_station_id VARCHAR(100),
                    start_geofence_name VARCHAR(200),
                    end_geofence_name VARCHAR(200),                                                                                    
                    PRIMARY KEY (trip_id))
            END     
        """)
    
    connect.commit()

    connect = connect(connection_string)
    
    cursor = connect.cursor()

    insert_sql = """
    INSERT INTO trips (
        device_id,
        distance,
        duration,
        end_time,
        provider_id,
        start_time,
        trip_id,
        trip_type,
        end_lat,
        end_lon,
        start_lat,
        start_lon,
        start_station_name,
        start_station_id,
        end_station_name,
        end_station_id,
        start_geofence_name,
        end_geofence_name
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    data = list(trips_df.itertuples(index=False, name=None))

    cursor.executemany(insert_sql, data)

    connect.commit()
        


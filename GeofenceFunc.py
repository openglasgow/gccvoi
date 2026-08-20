import requests
import pandas as pd
from datetime import datetime, timedelta
import sqlalchemy
from sqlalchemy import create_engine, text

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

def get_geofence(geofence_url: str,
                            access_token: str) -> pd.DataFrame:


    geofence_headers = {
        "Authorization": f"Bearer {access_token}"
    }

    geofence_response = requests.get(geofence_url, headers=geofence_headers)
    geofence_response.raise_for_status()

    geofence_json = geofence_response.json()

    df = pd.json_normalize(geofence_json["data"]["geofencing_zones"]['features'])

    df = df[df['geometry.type'] == 'MultiPolygon']

    df['geofence_name'] = df['properties.name'].apply(
    lambda x: x[0]['text'] if x else None)

    expand = df['properties.rules'].apply(
        lambda x: x[0] if isinstance(x, list) and
        len(x) > 0 else {}).apply(pd.Series)

    df = pd.concat([df, expand], axis = 1)

    df = df.drop(columns= ["properties.rules", "properties.name",])

    df['timestamp'] = datetime.now()

    df['geofence_name'] = df["geofence_name"].str.replace(
    "Glasgow - ", "", regex=False)

    df = df.drop(columns = ['geometry.type', 'geometry.coordinates'])

    print("Queries - Compiled") 

    return df

TOKEN_URL = "https://api.voiapp.io/v1/partner-apis/token"
API_KEY = "MDI5OTk5M2MtYTFhMC00M2E5LThlNzMtMzkzZTk5YjZiMzViOkRMNHdhVjRZMjQwew=="
GEOFENCE_URL = "https://api.voiapp.io/v1/partner-apis/gbfs/397/geofencing_zones.json"

#engine = create_engine("sqlite:///voi_cycles_database.db")
#with engine.begin() as connect:
    #connect.execute(text("""DROP TABLE geofence"""))

def run_geofence():
    token = get_access_token(TOKEN_URL, API_KEY)

    geofence_df = get_geofence(
    geofence_url=GEOFENCE_URL,
    access_token=token)
    
    print('Data Queried')

    #geofence_df.to_csv('geofence.csv', index = False)
    
    engine = create_engine("sqlite:///voi_cycles_database.db")

    with engine.begin() as connect:
        connect.execute(text("""
        CREATE TABLE IF NOT EXISTS geofence (
                             type TEXT,
                             geofence_name TEXT,
                             ride_end_allowed BOOLEAN,
                             ride_start_allowed BOOLEAN,
                             ride_through_allowed,
                             station_parking BOOLEAN,
                             maximum_speed_kph INT,
                             timestamp DATETIME,
                             PRIMARY KEY (geofence_name, timestamp));
    """))
    
    geofence_df.to_sql(
        "geofence",
        con=engine,
        if_exists="append",
        index=False
    )
    
    print('Database created')

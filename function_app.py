import logging
import azure.functions as func
# HTTP Packages
import pandas as pd
from mssql_python import connect
import os

from dotenv import load_dotenv

load_dotenv()

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

app = func.FunctionApp()

#@app.timer_trigger(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=False,use_monitor=False) 

#def Station_info_recent_timer_trigger(myTimer: func.TimerRequest):
#    run_station_information_recent()


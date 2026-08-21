
import azure.functions as func
from StationInfoFunc import run_station_information
from StationInfoRecentFunc import run_station_information_recent
from StationStatusFunc import run_station_status
from StationStatusRecentFunc import run_station_status_recent
from TripsFuncDaily import run_trips_daily
from TripsFunc import run_trips
from EventsRecentFunc import run_events_recent
from EventsHistoricalDailyFunc import run_events_historical_daily
from EventsHistoricalFunc import run_events_historical
from GeofenceFunc import run_geofence




app = func.FunctionApp()

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=False,use_monitor=False) 

def Station_info_recent_timer_trigger(myTimer: func.TimerRequest):
    run_station_information_recent()

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=False,use_monitor=False) 

def Station_info_timer_trigger(myTimer: func.TimerRequest):
    run_station_information()    

@app.timer_trigger(schedule= "0 */5 * * * *", arg_name= "myTimer", run_on_startup=False, use_monitor=False)

def Station_status_timer_trigger(myTimer: func.TimerRequest):
    run_station_status()

@app.timer_trigger(schedule= "0 */5 * * * *", arg_name= "myTimer", run_on_startup=False, use_monitor=False)

def Station_status_recent_timer_trigger(myTimer: func.TimerRequest):
    run_station_status_recent()    

@app.timer_trigger(schedule="0 0 2 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False)

def Trips_timer_trigger(myTimer: func.TimerRequest):
    run_trips_daily()

@app.function_name(name="HTTP_Trips_Trigger")
@app.route(route="run_trips", auth_level=func.AuthLevel.ANONYMOUS)
def HTTP_Trips_Trigger(req: func.HttpRequest) -> func.HttpResponse:
    run_trips()


@app.timer_trigger(schedule="0 1 * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False)

def Events_recent_timer_trigger(myTimer: func.TimerRequest):
    run_events_recent()

@app.timer_trigger(schedule="0 0 2 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False)

def Events_historical_timer_trigger(myTimer: func.TimerRequest):
    run_events_historical_daily()

@app.function_name(name="HTTP_Events_Historical_Trigger")
@app.route(route="run_events_historical", auth_level=func.AuthLevel.ANONYMOUS)
def HTTP_Events_Historical_Trigger(req: func.HttpRequest) -> func.HttpResponse:
    run_events_historical()    

@app.timer_trigger(schedule="0 0 2 * * *", arg_name="myTimer", run_on_startup=False,use_monitor=False) 

def Geofence_timer_trigger(myTimer: func.TimerRequest):
    run_geofence()


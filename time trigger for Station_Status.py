import azure.functions as func
from StationStatusFunc import run_station_status

app2 = func.FunctionApp()

@app2.timer_trigger(
    schedule="0 */5 * * * *",   # Every 5 mins
    arg_name="myTimer",
    run_on_startup=False
)
def station_status_timer(myTimer: func.TimerRequest):

    run_station_status()
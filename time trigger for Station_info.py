import azure.functions as func
from StationInfoFunc import run_station_information

app = func.FunctionApp()

@app.timer_trigger(
    schedule="0 */5 * * * *",   # Every 5 min
    arg_name="myTimer",
    run_on_startup=False
)
def station_info_timer(myTimer: func.TimerRequest):

    run_station_information()



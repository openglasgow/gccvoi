import azure.functions as func
from VehicleStatusFunc import run_vehicle_status

app3 = func.FunctionApp()

@app3.timer_trigger(
    schedule="0 */5 * * * *",   # Every 5 mins
    arg_name="myTimer_vehicle",
    run_on_startup=False
)
def vehicle_status_timer(myTimer_vehicle: func.TimerRequest):
 
    run_vehicle_status()
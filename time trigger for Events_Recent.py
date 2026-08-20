import azure.functions as func
from EventsRecentFunc import run_events_recent

app5 = func.FunctionApp()

@app5.timer_trigger(
    schedule="0 1 * * * *",   # Every hour
    arg_name="myTimer_events_recent",
    run_on_startup=False
)
def events_recent_timer(myTimer_events_recent: func.TimerRequest):

    run_events_recent()
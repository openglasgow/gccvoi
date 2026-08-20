import azure.functions as func
from EventsHistoricalDailyFunc import run_events_historical_daily

app6 = func.FunctionApp()

@app6.timer_trigger(
    schedule="0 0 2 * * *",   # Every day at 2am
    arg_name="myTimer_events_historical",
    run_on_startup=False
)
def events_historical_timer(myTimer_events_historical: func.TimerRequest):

    run_events_historical_daily()
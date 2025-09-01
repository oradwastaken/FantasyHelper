from datetime import date, timedelta


def get_previous_monday():
    today = date.today()
    days_since_monday = today.weekday() % 7
    days_to_subtract = 7 if days_since_monday == 0 else days_since_monday
    previous_monday = today - timedelta(days=days_to_subtract)
    return previous_monday.strftime("%Y-%m-%d")

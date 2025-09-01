from datetime import date, timedelta


def get_previous_monday() -> str:
    today = date.today()
    days_since_monday = today.weekday() % 7
    days_to_subtract = 7 if days_since_monday == 0 else days_since_monday
    previous_monday = today - timedelta(days=days_to_subtract)
    return previous_monday.strftime("%Y-%m-%d")


def get_current_season() -> str:
    """
    Returns the season string in the format "YYYYYYYY".
    - Season runs from Oct 1 of year N to Sept 30 of year N+1.
    """
    current_date = date.today()
    year = current_date.year

    # If date is before Oct 1, it's still part of the previous season
    if current_date < date(year, 10, 1):
        start_year = year - 1
    else:
        start_year = year

    end_year = start_year + 1
    return f"{start_year}{end_year}"

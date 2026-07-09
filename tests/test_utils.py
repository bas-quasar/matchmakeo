from datetime import date, datetime

from matchmakeo.utils import daterange

def test_daterange():

    # test with dates as date objects
    start_date = date(2025, 8, 1)
    end_date = date(2025, 8, 5)

    dr = daterange(start_date, end_date)
    assert next(dr) == start_date

    dates = []
    for d in daterange(start_date, end_date):
        dates.append(d)

    assert dates[0] == start_date
    assert dates[-1] == end_date
    assert len(dates) == 5

from datetime import date, datetime, timedelta
import json
import logging

from pandas import Timestamp
import shapely

__all__ = [
    "setUpLogging",
    "coords_to_polygon",
    "daterange",
    "infer_sql_type",
]

def setUpLogging(module_name = __name__):
    logger = logging.getLogger(module_name)
    FORMAT = "[%(filename)s . %(funcName)20s() ] %(message)s"
    logging.basicConfig(format=FORMAT)
    return logger

log = setUpLogging(__name__)

def coords_to_polygon(coords:list[tuple[float]]) -> str:
    """Takes an iterable of coordinate pairs and returns a WKT POLYGON string."""
    return shapely.Polygon(coords).wkt

def geojon_to_polygon(geometry:str) -> str:
    """Takes a geojson geometry and returns a WKT POLYGON string."""
    return shapely.from_geojson(json.dumps(geometry)).wkt

def daterange(start_date:date|str, end_date:date|str):
    """Returns a sequence of dates separated by one day. Inclusive of start and end date."""

    date_format_string = "%Y-%m-%d"

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, date_format_string).date()

    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, date_format_string).date()

    days = int((end_date - start_date).days)  + 1
    for n in range(days):
        yield start_date + timedelta(n)

def infer_sql_type(val) -> str:
    """"Takes a value and returns the appropriate SQL type."""

    if isinstance(val, float):
        return "FLOAT"
    elif isinstance(val, bool):
        return "BOOLEAN"
    elif isinstance(val, int):
        return "BIGINT"
    elif isinstance(val, str):
        return "TEXT"
    elif isinstance(val, dict) or isinstance(val, list):
        return "JSON"
    elif isinstance(val, Timestamp):
        return "TIMESTAMP"
    elif isinstance(val, shapely.geometry.Polygon):
        return "GEOMETRY(POLYGON, 4326)"
    elif val is None:
        log.warning("Unknown type for: None")
    else:
        log.warning(f"Unknown type for: {val}")

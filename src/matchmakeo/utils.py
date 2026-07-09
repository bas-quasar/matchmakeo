from datetime import date, datetime, timedelta
import json
import logging
import multiprocessing
import os

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

def daterange(start_date:date, end_date:date):
    """Returns a sequence of dates separated by one day. Inclusive of start and end date."""

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

def get_optimal_workers(default_per_core=2, maximum_cap=10):
    """
    Determines max_workers dynamically based on environment, 
    hardware, and system limits.
    """
    # if MAX_WORKERS env var set
    env_workers = os.environ.get("MAX_WORKERS")
    if env_workers:
        try:
            return int(env_workers)
        except ValueError:
            pass 

    # fall back on slurm env vars
    hpc_cpus = os.environ.get("SLURM_CPUS_PER_TASK") or os.environ.get("SLURM_JOB_CPUS_PER_NODE")
    if hpc_cpus:
        return int(hpc_cpus)
    
    # Local Hardware Fallback (Laptops / Workstations)
    try:
        # Detects real available cores (handles cgroups/Docker constraints properly)
        cores = len(os.sched_getaffinity(0))
    except AttributeError:
        # Fallback for Windows/macOS where sched_getaffinity doesn't exist
        cores = multiprocessing.cpu_count()
        
    # For I/O bound can usually run more threads than raw physical CPU cores.
    calculated_workers = cores * default_per_core
    
    # Cap it on local machines so we don't overwhelm the network interface
    return min(calculated_workers, maximum_cap)

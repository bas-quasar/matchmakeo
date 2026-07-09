from dataclasses import dataclass, field
import datetime
from datetime import date

__all__ = [
    "Queryset",
    "NasaCMRQueryset",
    "EarthEngineQueryset",
    "JaxaGportalQueryset",
]

@dataclass(kw_only=True)
class Queryset:
    "Generic query parameters to be used in a catalogue request."

    start_date: date
    end_date: date
    lat_max: float = +90
    lat_min: float = -90
    lon_max: float = +180
    lon_min: float = -180
    date_format: str = "%Y-%m-%d"

    def __post_init__(self):

        date_fields = ["start_date", "end_date"]
        
        for field in date_fields:
            current_value = getattr(self, field)
            
            if isinstance(current_value, str):
                parsed_date = datetime.datetime.strptime(current_value, self.date_format).date()
                setattr(self, field, parsed_date)

@dataclass(kw_only=True)
class NasaCMRQueryset(Queryset):
    "Extends the base Queryset with parameters specific to NASA CMR queries."
    
    page_size: int = 200

@dataclass(kw_only=True)
class EarthEngineQueryset(Queryset):
    "Extends the base Queryset with parameters specific to Google Earth Engine queries."

@dataclass(kw_only=True)
class JaxaGportalQueryset(Queryset):
    """
    Extends the base Queryset with parameters specific to JAXA G-Portal queries.

    params is a dictionary containing additional keys and values for JAXA G-Portal queries
    see: https://gportal.jaxa.jp/gpr/assets/mng_upload/COMMON/upload/GPortalUserManual_en.pdf appendix 7

    e.g. {
        "acquisitionType": "NOMINAL",
        "polarisationChannels": "HH",
    }
    """

    params:dict = field(default_factory=dict)
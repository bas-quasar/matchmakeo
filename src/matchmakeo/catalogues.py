from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
import itertools
import json
import logging
from pathlib import Path
import os
from tempfile import TemporaryFile
import warnings

from geoalchemy2 import Geometry
import requests
from shapely import Polygon
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, Float, Connection
from tqdm import tqdm

# optional dependencies
try:
    import gportal
except:
    gportal = None

try:
    import ee
except:
    ee = None

try:
    import google.auth
except:
    pass

from .databases import Database
from .field import Field
from .product import Product
from .queryset import Queryset, NasaCMRQueryset, EarthEngineQueryset, JaxaGportalQueryset
from .utils import coords_to_polygon, setUpLogging, geojon_to_polygon, get_optimal_workers


log = logging.getLogger(__name__)


__all__ = [
    "Catalogue",
    "NasaCMR",
    "EarthEngine",
]


class Catalogue(ABC):
    """Abstract Base Class for defining catalogue interfaces.
    Do not call this class directly. Subclass it and define methods.
    """

    def __init__(self, queryset_type: Queryset = None):
        
        self.fields = []
        
        if queryset_type:
            self.queryset_type = queryset_type


    def download_footprints(self,
                product: Product,
                queryset: Queryset,
                database: Database = None,
                primary_key:str = "id",
                dry_run:bool = False,
                ):
        """Abstract method"""
        self._check_queryset_type(queryset=queryset)
        self._check_database_dryrun(database, dry_run)
    
    def _check_queryset_type(self, queryset:Queryset):
        """Raise UserWarning if queryset type does not match catalogue type."""
        if type(queryset) is not self.queryset_type:
            warnings.warn(f"Queryset of type {self.queryset_type} is advised. Got {type(queryset)} instead. Some features may not work as intended.",
                          UserWarning)
            
    def _check_database_dryrun(self, database:Database, dry_run:bool):
        """Raise UserWarning if not dry_run and no database specified"""
        if not dry_run and not Database:
            warnings.warn(f"Got dry_run: {dry_run} and database: {database}. Database needed unless dry_run=True.")
            
    def _create_table(self, connection:Connection, product:Product, primary_key:str='pk'):

        log.info(f"Creating table {product.table}")

        metadata = MetaData()
        table = Table(product.table, metadata,
            Column(primary_key, Integer, primary_key=True),
            *[f._as_column() for f in self.fields],
            *[f._as_column() for f in product.extra_fields],
        )

        table.create(connection, checkfirst=True)
        connection.commit()

        return table


class NasaCMR(Catalogue):
    """Interface to download from the NASA Common Metadata Repository (CMR) (<https://cmr.earthdata.nasa.gov/>) for all Earth Observing System Data and Information System (EOSDIS) metadata including MODIS footprints."
    Note: User accounts and hence access to restricted data are not currently supported.
    """

    def __init__(self,
                 client_id: str = None,
                 url:str = "https://cmr.sit.earthdata.nasa.gov/search/granules.json", #"https://cmr.earthdata.nasa.gov/search/granules.json",
                 queryset_type: Queryset = NasaCMRQueryset,
                 ):
        """_summary_
        Params:
            client_id(str): Client ids are strongly encouraged by NASA CMR, we suggest using your name or research group.
        """

        self.url = url

        super().__init__(queryset_type=queryset_type)

        if client_id is None:
            log.warning("No client_id set. Client ids are strongly encouraged by NASA CMR, we suggest using your name or research group's name, for example.")

        # add fields specific to this catalogue
        additional_fields = [
            Field('id', 'id', String),
            Field('geometry', 'geometry', Geometry('POLYGON', srid=4326)),
            Field('datetime_start', 'datetime_start', DateTime),
            Field('datetime_end', 'datetime_end', DateTime),
        ]
        self.fields.extend(additional_fields)

    def download_footprints(self,
                product: Product,
                queryset: Queryset,
                database: Database,
                primary_key:str = "id",
                dry_run: bool = False,
                ):
        super().download_footprints(product=product, queryset=queryset, database=database, dry_run=dry_run, primary_key=primary_key)

        if dry_run:
            log.warning("dry_run enabled, skipping database operations")
        else:
            try:
                connection = database.connect()
            except ConnectionError:
                raise ConnectionError(f"Database connection failed. Aborting.")

            table = self._create_table(connection, product)

        # initialisation
        response = None
        headers = {}
        granules = []

        # iterate through pages of data using Search-After
        while True:
            # Query parameters
            params = {
                "short_name": product.name,
                "page_size": queryset.page_size,
                'temporal': f"{queryset.start_date.strftime('%Y-%m-%d')}T00:00:00Z,{queryset.end_date.strftime('%Y-%m-%d')}T00:00:00Z",
                "bounding_box": self._get_bounding_box(queryset),
            }

            if product.version:
                params.update({"version": self.product.version})

            if getattr(queryset, "concept_id", None):
                params.update(self.queryset.concept_id)

            # if there is a previous response, check for additional available pages
            # as recommended by CMR https://wiki.earthdata.nasa.gov/display/CMR/CMR+Harvesting+Best+Practices
            if response:

                # if previous response has CMR-Search-After header, add details to request headers
                search_after = response.headers.get("CMR-Search-After", None)
                if search_after:
                    headers.update({
                        "CMR-Search-After": search_after,
                    })
                else:
                    # if there is a previous response and does not have CMR-Search-After header, there is no more data
                    break
            
            # Request granule metadata
            response = requests.get(self.url, params=params, headers=headers)

            if response.status_code != 200:
                log.info(f"Error: {response.text}")
                return

            results = response.json()

            log.debug(response.text)


            for item in results["feed"]["entry"]:

                coords = None
                for poly in item["polygons"][0]:
                    vals   =  list ( map (float, poly.split() ) )
                    coords = [list ( zip( vals[1::2], vals[::2] ) )]

                props = {}

                for prop in item:
                    if not prop in ["polygons"]:
                        props[prop] = item[prop]

                # TODO use a dictionary at least to store each footprint
                granules.append((coords, props))



        log.info(f"{len(granules)} footprints found for {params['temporal']}")

        if not dry_run:
            database.create_columns_from_footprint_props(table_name=product.table,
                                                        catalogue_fields=self.fields,
                                                        product_fields = product.extra_fields,
                                                        props=[g[1] for g in granules],
                                                        )
            
            metadata = MetaData()
            table = Table(product.table, metadata, autoload_with=connection.engine)

            for granule in granules:
                insertion = table.insert().values(
                    # id=granule[1]['id'],
                    geometry=coords_to_polygon(granule[0][0]),
                    datetime_start=datetime.fromisoformat(granule[1]['time_start']),
                    datetime_end=datetime.fromisoformat(granule[1]['time_end']),
                    **granule[1],
                    )
                connection.execute(insertion)
                connection.commit()


    def _get_bounding_box(self, queryset: Queryset) -> str:
        "Returns bounding box string for NASA CMR spatial query, using queryset lat and lon."

        # https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#g-bounding-box
        # 4 comma-separated numbers: lower left longitude, lower left latitude, upper right longitude, upper right latitude.

        return f"{min((queryset.lon_min, queryset.lon_max))},{min((queryset.lat_min, queryset.lat_max))},{max((queryset.lon_min, queryset.lon_max))},{max((queryset.lat_min, queryset.lat_max))}"

class EarthEngine(Catalogue):
    """Interface for downloading footprints from Google Earth Engine.

    Requires the earthengine-api package, install with `pip install matchmakeo[earthengine]` or `pip install earthengine-api`.

    """

    def __init__(
            self,
            project_id:str=None,
            service_account:bool = False,
            queryset_type:Queryset = EarthEngineQueryset,
            ):

        if not ee:
            raise ImportError("Earth Engine Catalogue interface requires the earthengine-api package, install with `pip install matchmakeo[earthengine]` or `pip install earthengine-api`.")

        if not project_id:
            raise ValueError(f"Earth Engine requires a project name. Got {project_id=}")

        self.initialise_earth_engine(project_id=project_id,service_account=service_account)

        super().__init__(queryset_type)

        # add fields specific to this catalogue
        additional_fields = [
            Field('id', 'id', String),
            Field('geometry', 'geometry', Geometry('POLYGON', srid=4326)),
        ]
        self.fields.extend(additional_fields)


    def initialise_earth_engine(self, project_id:str, service_account:bool=False):

        try:
            if service_account:
                credentials, _ = google.auth.default(scopes=['https://googleapis.com', 'https://googleapis.com'], quota_project_id=project_id)
                ee.Initialize(credentials, project=project_id)
            else:
                ee.Authenticate()
                ee.Initialize(project=project_id)
        except Exception as e:
            log.error("Earth Engine authentication failed.")
            raise Exception(e)


    def download_footprints(self, product, queryset, database, primary_key = "id", dry_run:bool=False):
        super().download_footprints(product, queryset, database, dry_run, primary_key)

        bbox = ee.Geometry.BBox(
            west=queryset.lon_min,
            south=queryset.lat_min,
            east=queryset.lon_max,
            north=queryset.lat_max,
            )


        def fetch_day_metadata(day_string):
            """
            Worker function executed in parallel. 
            Retrieves image asset metadata and geometries for a single day.
            """
            current_date = ee.Date(day_string)
            next_date = current_date.advance(1, 'day')
            
            # Filter the raw collection by Date and Spatial Bounds
            day_collection = (ee.ImageCollection(product.name)
                            .filterDate(current_date, next_date)
                            .filterBounds(bbox))
            
            # Convert the ImageCollection into a FeatureCollection.
            # converts each image's spatial footprint into a feature geometry
            # while keeping all of the image's metadata.
            metadata_features = ee.FeatureCollection(day_collection)
            
            # Filter properties to keep the payload small
            # metadata_features = metadata_features.select(
            #     propertySelectors=['system:index', 'system:time_start', 'CLOUDY_PIXEL_PERCENTAGE'], 
            #     retainGeometry=True # Keeps the polygon boundary layout of the scene
            # )
            
            # Fetch data
            try:
                data = metadata_features.getInfo()
                return day_string, data.get('features', [])
            except Exception as e:
                print(f"Error processing date {day_string}: {e}")
                return day_string, []

        if not dry_run:
            log.info(f"Connecting to database at {database}.")
            try:
                connection = database.connect()
            except ConnectionError:
                raise ConnectionError(f"Connection to {database} failed. Aborting.")

            table = self._create_table(connection, product)

        delta = queryset.end_date - queryset.start_date
        start = queryset.start_date
        
        daily_strings = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(delta.days)]
        
        with ThreadPoolExecutor(max_workers=get_optimal_workers()) as executor:
            results = executor.map(fetch_day_metadata, daily_strings)
            
            for date_str, granules in results:
                if not granules:
                    log.info(f"{date_str}: No images intersected the bounds.")
                    continue
                    
                log.info(f"{date_str}: Found {len(granules)} images.")
                
                if dry_run:
                    log.info(f"dry_run: {dry_run}, skipping database insertion.")
                else:


                    # 'flatten' the properties
                    props = []
                    for g in granules:
                        p = g['properties']
                        p.update({
                            'id': g.get('id'),
                            'version': g.get('version'),
                            'type': g.get('type'),
                            'bands': g.get('bands'),
                        })
                        props.append(p)

                    database.create_columns_from_footprint_props(table_name=product.table,
                                                                catalogue_fields=self.fields,
                                                                product_fields = product.extra_fields,
                                                                props=props,
                                                                )
                    
                    metadata = MetaData()
                    table = Table(product.table, metadata, autoload_with=connection.engine)

                    for granule in granules:
                        insertion = table.insert().values(
                            # id=granule['id'],
                            geometry=coords_to_polygon(granule['properties']['system:footprint']['coordinates']),
                            # type=granule.get('type'),
                            # version=granule.get('version'),
                            # bands=granule.get('bands'),
                            **granule.get('properties'),
                            )
                        connection.execute(insertion)
                        connection.commit()


class JaxaGportal(Catalogue):
    """Interface for downloading footprints from JAXA G-Portal.

    Requires the gportal-python package install with `pip install matchmakeo[gportal]` or `pip install gportal`.

    Product name should be a value in gportal.datasets(),
    e.g. gportal.datasetts()["GCOM-W/AMSR2"]["LEVEL1"]["L1R-Brightness temperature(TB)"]
    or "11001002"

    """

    def __init__(self, queryset_type:Queryset = JaxaGportalQueryset, username=os.getenv("GPORTAL_USERNAME", None), password=os.getenv("GPORTAL_PASSWORD", None)):
        if not gportal:
            raise ImportError("JAXA G-Portal Catalogue interface requires the gportal package, install with `pip install matchmakeo[gportal]` or `pip install gportal`.")

        super().__init__(queryset_type)

        if username or password is None:
            log.error("Got None for either username or password, these must be passed as arguments or set via the environment variables GPORTAL_USERNAME and GPORTAL_PASSWORD.")


        additional_fields = [
            Field('identifier', 'id', String),
            Field('geometry', 'geometry', Geometry('POLYGON', srid=4326)),
            Field('beginPosition', 'datetime_start', DateTime),
            Field('endPosition', 'datetime_end', DateTime),
        ]
        self.fields.extend(additional_fields)

    def download_footprints(self, product:Product, queryset:Queryset, database:Database=None, primary_key:str = "id", dry_run:bool=False):
        super().download_footprints(product, queryset, database, primary_key, dry_run)

        try:
            import gportal
        except ImportError:
            raise ImportError("JAXA G-Portal Catalogue interface requires the gportal package, install with `pip install matchmakeo[gportal]` or `pip install gportal`.")

        if dry_run:
            log.warning("dry_run enabled, skipping database operations")
        else:
            try:
                connection = database.connect()
            except ConnectionError:
                raise ConnectionError(f"Database connection failed. Aborting.")

            table = self._create_table(connection, product)

        search_results = gportal.search(
            dataset_ids=[product.name] if isinstance(product.name, str) else product.name,
            start_time=queryset.start_date,
            end_time=queryset.end_date,
            bbox=[queryset.lon_min, queryset.lat_min, queryset.lon_max, queryset.lat_max],
            params=queryset.params,
        )

        log.info(f"Found {search_results.matched()}")
        if dry_run:
            return search_results

        if not search_results.products():
            log.warning("No products found.")
            return None
        
        if not dry_run:
            database.create_columns_from_footprint_props(table_name=product.table,
                                                        catalogue_fields=self.fields,
                                                        product_fields = product.extra_fields,
                                                        props=[p.properties for p in search_results.products()],
                                                        )
            
            metadata = MetaData()
            table = Table(product.table, metadata, autoload_with=connection.engine)

            for prod in search_results.products():
                print(prod.to_dict())
                # properties example:
                # {'identifier': 'GW1AM2_202001010047_189D_L1SGRTBR_2220220', 'acquisitionType': 'NOMINAL', 'processingDate': '2020-01-01T02:53:36.000Z', 'processingLevel': 'AMSR2-L1R', 'processorVersion': '220,220', 'status': 'ARCHIVED', 'beginPosition': '2020-01-01T00:47:00.855Z', 'endPosition': '2020-01-01T01:36:21.574Z', 'platformShortName': 'GCOM-W1', 'instrumentShortName': 'AMSR2', 'wrsLongitudeGrid': 189, 'lastOrbitNumber': 40552, 'ascendingNodeDate': '2020-01-01T01:13:46.699Z', 'ascendingNodeLongitude': 3.81, 'multiExtentOf': '-176.886 84.355 139.298 86.437 103.605 83.761 102.901 79.831 110.928 76.268 121.735 73.532 117.055 73.948 112.168 74.257 107.127 74.455 101.996 74.534 96.852 74.498 91.769 74.341 63.323 70.726 46.055 64.290 35.785 56.614 26.568 44.128 20.757 31.106 16.562 17.820 10.550 -8.590 8.050 -22.133 5.735 -35.670 3.482 -49.183 1.934 -58.166 0.220 -67.125 -2.200 -76.059 -2.673 -77.399 -3.219 -78.739 -3.867 -80.077 -4.647 -81.415 -5.677 -82.750 -7.109 -84.082 -48.629 -86.429 -87.348 -83.868 -88.771 -79.846 -80.939 -76.150 -70.123 -73.278 -65.770 -72.766 -61.722 -72.153 -57.943 -71.464 -54.422 -70.709 -51.166 -69.892 -48.161 -69.020 -33.274 -62.206 -24.171 -54.387 -18.077 -46.085 -11.827 -33.164 -7.387 -19.934 -3.911 -6.531 1.498 19.964 3.900 33.510 6.240 47.039 8.732 60.543 10.701 69.522 13.831 78.490 29.726 87.356 47.611 88.561 113.749 89.120 162.142 88.237 174.920 86.989 -179.790 85.681 -176.886 84.355', 'product': {'fileName': 'https://gportal.jaxa.jp/download/standard/GCOM-W/GCOM-W.AMSR2/L1R/2/2020/01/GW1AM2_202001010047_189D_L1SGRTBR_2220220.h5', 'size': 51065652, 'version': 2}, 'browse': [{...}, {...}], 'gpp': {'datasetId': 11001002, 'totalQualityCode': 'Good', 'physicalQuantity': 'Brightness Temperature', 'parameterVersion': 220, 'algorithmVersion': 220, 'numberMissingData': 0, 'startPathNumber': 189, 'endPathNumber': 189, 'mapProjection': None, 'orbitDirection': 'Descending', 'pseq': 'EQ', 'topicCategory': '-', 'organizationName': 'JAXA', 'hasProduct': True}}
                insertion = table.insert().values(
                    geometry=geojon_to_polygon(prod.geometry),
                    datetime_start=datetime.fromisoformat(prod.properties['beginPosition']),
                    datetime_end=datetime.fromisoformat(prod.properties['endPosition']),
                    **{k: v for k, v in prod.properties.items() if k not in [f.catalogue_name for f in self.fields + product.extra_fields]}
                    )
                connection.execute(insertion)
                connection.commit()



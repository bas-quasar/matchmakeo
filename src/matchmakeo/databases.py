from abc import ABC
from dataclasses import dataclass
from pathlib import Path
import os

from geoalchemy2 import Geometry
from geopandas import GeoDataFrame
from sqlalchemy import create_engine, Engine, Connection, Table, MetaData

from .field import Field
from .utils import infer_sql_type, setUpLogging

log = setUpLogging(__name__)

class Database(ABC):

    """Abstract class for database connections.

    db_url (str): full custom connect string for database, will be used if specified
    """
    def __init__(self,
                database: str,
                username: str,
                password: str,
                host: str = "localhost",
                port: int = 5432,
                dialect: str = None,
                driver: str = None,
                db_url: str = None,
            ):
        self.database = database
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.dialect = dialect
        self.driver = driver
        self.db_url = db_url
        
        self.engine = None
        self.connection = None
        self.metadata = MetaData()

    def __str__(self):
        return self.url

    @property
    def url(self):
        if self.db_url:
            return self.db_url
        else:
            if self.driver:
                dialect_driver = f"{self.dialect}+{self.driver}"
            else:
                dialect_driver = self.dialect

            return f"{dialect_driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def create_engine(self) -> Engine:
        self.engine = create_engine(
            self.url,
            echo=False,
            plugins=["geoalchemy2"],
        )
        return self.engine
    
    def connect(self) -> Connection:
        if self.engine:
            try:
                self.connection = self.engine.connect()
            except ConnectionError:
                raise ConnectionError(f"Database connection failed. Aborting.")
            
            return self.connection
        
        else:
            log.info(f"No connection available yet. Trying to connect to {self.url}")
            self.create_engine()
            return self.connect()

    def write_gdf(self, gdf:GeoDataFrame, table:str): ...

    def create_columns_from_footprint_props(
            self,
            table_name:str,
            catalogue_fields:list[dict],
            product_fields:list[dict],
            props:list[dict],
            ): ...

class PostGISDatabase(Database):
    """Database connection for PostGIS databases.
    """

    def __init__(
            self,
            database,
            username,
            password,
            host = "localhost",
            port = 5432,
            db_url = None,
            dialect = "postgresql",
            driver = "psycopg",
            ):

        super().__init__(
            database,
            username,
            password,
            host,
            port,
            db_url=db_url,
            dialect=dialect,
            driver=driver,
            )
        
    def write_gdf(self, gdf: GeoDataFrame, table:str):
        engine = self.create_engine()
        gdf.to_postgis(table, engine)

    def create_columns_from_footprint_props(
            self,
            table_name:str,
            catalogue_fields:list[dict],
            product_fields:list[dict],
            props:list[dict],
            ):
        
        # get the existing table and its columns
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=self.engine)
        existing_column_names = set([c.name for c in table.columns])

        gdf = GeoDataFrame(props)
        properties = gdf.iloc[0].to_dict()

        #TODO test

        # get the corresponding *catalogue* names for all fields with names and types defined internally or by the user
        predefined_fields_catalogue_names = [c.catalogue_name for c in catalogue_fields + product_fields]

        # work out which fields are in the data but are NOT already defined above
        extra_fields = [f for f in list(properties.keys()) if f not in predefined_fields_catalogue_names]

        # get the *column* names
        all_required_column_names = set([c.column_name for c in catalogue_fields + product_fields] + extra_fields)

        # if all the columns we need already exist
        if existing_column_names.issuperset(all_required_column_names):
            return
        else:
            raw_connection = self.create_engine().raw_connection()
            cursor = raw_connection.cursor()
            # create new columns with types for any which do not already exist
            for col_name in all_required_column_names.difference(existing_column_names):
                data = properties.get(col_name, None)
                if data is not None:
                    sql_col_type = infer_sql_type(data)
                    sql_cmd = f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "{col_name}" {sql_col_type};'
                    cursor.execute(sql_cmd)
            
            raw_connection.commit()
            raw_connection.close()
        
class SpatialiteDatabase(Database):

    def __init__(
        self,
        filename: str|Path = None,
        db_url: str = None,
        dialect: str = "sqlite",
        ):
        
        if bool(db_url) == bool(filename):
            raise ValueError(f"Got {db_url=} and {filename=}, you must set *one* of db_url *or* filename")
        else:
            self.db_url = db_url
            self.filename = filename

        os.environ["SPATIALITE_LIBRARY_PATH"] = "mod_spatialite"

        super().__init__(
            database=None,
            username=None,
            password=None,
            host=None,
            port=None,
            db_url=db_url,
            dialect=dialect,
            driver=None,
            )
        
    @property
    def url(self):
        # sqlite/spatialite connect strings/urls take a different format to standard so this class has a custom url prop method
        if self.db_url:
            return self.db_url
        elif self.filename:
            return f"sqlite:///{self.filename}"
        
    def connect(self):
        log.info(f"Connecting to {self.url}. Note that creating a new db can take a few minutes.")
        return super().connect()
    
    def write_gdf(self, gdf:GeoDataFrame, table:str):
        gdf.to_file(self.filename, driver='SQLite', spatialite=True)

    def create_columns_from_footprint_props(
            self,
            table_name:str,
            catalogue_fields:list[dict],
            product_fields:list[dict],
            props:list[dict],
            ):
        
        # get the existing table and its columns
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=self.engine)
        existing_column_names = set([c.name for c in table.columns])

        gdf = GeoDataFrame(props)
        properties = gdf.iloc[0].to_dict()

        #TODO test

        # get the corresponding *catalogue* names for all fields with names and types defined internally or by the user
        predefined_fields_catalogue_names = [c.catalogue_name for c in catalogue_fields + product_fields]

        # work out which fields are in the data but are NOT already defined above
        extra_fields = [f for f in list(properties.keys()) if f not in predefined_fields_catalogue_names]

        # get the *column* names
        all_required_column_names = set([c.column_name for c in catalogue_fields + product_fields] + extra_fields)

        # if all the columns we need already exist
        if existing_column_names.issuperset(all_required_column_names):
            return
        else:
            raw_connection = self.create_engine().raw_connection()
            cursor = raw_connection.cursor()
            # create new columns with types for any which do not already exist
            for col_name in all_required_column_names.difference(existing_column_names):
                data = properties.get(col_name, None)
                if data is not None:
                    sql_col_type = infer_sql_type(data)
                    sql_cmd = f'ALTER TABLE {table_name} ADD COLUMN "{col_name}" {sql_col_type};'
                    cursor.execute(sql_cmd)
            
            raw_connection.commit()
            raw_connection.close()
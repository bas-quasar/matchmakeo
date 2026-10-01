import datetime
import json
import os
import uuid
from contextlib import closing

import pytest
from geoalchemy2 import Geometry
from pytest_databases.docker.postgres import PostgresService
from sqlalchemy import Column, DateTime, Integer, MetaData, Table, create_engine, text

from matchmakeo import Product
from matchmakeo.databases import PostGISDatabase, SpatialiteDatabase

try:
    import sqlite3
except ImportError:
    sqlite3 = None

pytest_plugins = [
    "pytest_databases.docker.postgres",
]


@pytest.fixture(scope="module", params=["postgis", "spatialite"])
def database(request):
    backend = request.param

    if backend == "postgis":
        postgres_service = request.getfixturevalue("postgres_service")
        db = PostGISDatabase(
            database=postgres_service.database,
            username=postgres_service.user,
            password=postgres_service.password,
            host=postgres_service.host,
            port=postgres_service.port,
        )
        yield db
        db.close()

    elif backend == "spatialite":
        spatialite_url = request.getfixturevalue("spatialite_url")
        db = SpatialiteDatabase(
            db_url=spatialite_url,
        )
        yield db
        # Properly disposes engine and closes active connections before pytest-cov GC runs
        db.close()
    else:
        raise ValueError(f"Backend type {backend} not supported.")


@pytest.fixture(scope="session")
def postgres_image() -> str:
    return "postgis/postgis:16-3.5"


@pytest.fixture(scope="session", autouse=True)
def init_test_database(postgres_service: PostgresService):
    # Construct the connection URL
    db_url = (
        f"postgresql+psycopg://{postgres_service.user}:{postgres_service.password}@"
        f"{postgres_service.host}:{postgres_service.port}/{postgres_service.database}"
    )

    # Create a temporary engine just to activate PostGIS
    engine = create_engine(db_url)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))

    engine.dispose()


def find_spatialite_extension():
    """Attempts to return the path to the spatialite extension across a few different operating systems."""
    if not sqlite3:
        raise RuntimeError("sqlite3 package not available. Exiting.")
    paths = [
        "mod_spatialite",
        "mod_spatialite.so",
        "/usr/lib/x86_64-linux-gnu/mod_spatialite.so",
        "/opt/homebrew/lib/mod_spatialite.dylib",
        "/usr/local/lib/mod_spatialite.dylib",
    ]
    for path in paths:
        try:
            with closing(sqlite3.connect(":memory:")) as conn:
                conn.enable_load_extension(True)
                conn.load_extension(path)
                return path
        except sqlite3.OperationalError:
            continue
    raise RuntimeError("SpatiaLite extension not found.")


@pytest.fixture(scope="session")
def spatialite_url():
    if not sqlite3:
        raise RuntimeError("sqlite3 package not available. Exiting.")

    db_name = f"test_geo_{uuid.uuid4().hex}"
    url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"

    raw_url = f"file:{db_name}?mode=memory&cache=shared"
    keep_alive_conn = sqlite3.connect(raw_url, uri=True)

    try:
        keep_alive_conn.enable_load_extension(True)
        keep_alive_conn.load_extension(find_spatialite_extension())
        keep_alive_conn.execute("SELECT InitSpatialMetaData(1);")
        keep_alive_conn.commit()

        yield url
    finally:
        keep_alive_conn.close()


def _build_mock_product(db, fixtures_file, table_name, date_fields):
    """
    Generic helper to construct a dynamic table, insert JSON mock data,
    and return the metadata and Product instance for testing.
    """
    metadata = MetaData()

    columns = [
        Column("id", Integer, primary_key=True),
        Column("timestamp", DateTime, nullable=False),
        Column("geometry", Geometry("POLYGON", srid=4326), nullable=False),
    ]
    table = Table(table_name, metadata, *columns)
    db.create_engine()
    metadata.create_all(db.engine)

    records_to_insert = []
    with open(fixtures_file, "r") as f:
        fixture = json.load(f)
    for row in fixture:
        record = row.copy()

        for field in date_fields:
            if field in record:
                record[field] = datetime.datetime.fromisoformat(record[field])
        records_to_insert.append(record)

    with db.connect() as conn:
        conn.execute(table.insert(), records_to_insert)
        conn.commit()

    return metadata, Product(table_name)


def _product_fixture(database, product_name, filepath=None):
    """Helper generator function to encapsulate product fixture setup and teardown."""
    if filepath is None:
        filepath = os.path.join("tests", "fixtures", f"dummy_{product_name}.json")

    metadata, product = _build_mock_product(
        db=database,
        fixtures_file=filepath,
        table_name=product_name,
        date_fields=["timestamp"],
    )

    yield product
    metadata.drop_all(database.engine)


@pytest.fixture(scope="function")
def product_a(database, filepath=None):
    """Creates product_a table and populates it from JSON."""
    yield from _product_fixture(database, "product_a", filepath)


@pytest.fixture(scope="function")
def product_b(database, filepath=None):
    """Creates product_b table and populates it from JSON."""
    yield from _product_fixture(database, "product_b", filepath)

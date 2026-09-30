import uuid
from contextlib import closing

import pytest
from pytest_databases.docker.postgres import PostgresService
from sqlalchemy import create_engine, text

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

import uuid
import pytest
from sqlalchemy import create_engine, text
from pytest_databases.docker.postgres import PostgresService

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
        yield PostGISDatabase(
            database=postgres_service.database,
            username=postgres_service.user,
            password=postgres_service.password,
            host=postgres_service.host,
            port=postgres_service.port
        )
    elif backend == "spatialite":
        spatialite_url = request.getfixturevalue("spatialite_url")
        yield SpatialiteDatabase(
            db_url=spatialite_url,
        )
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
    """
    Attmpts to return the path to the spatialite extension across a few different operating systems.
    """
    if not sqlite3:
        raise RuntimeError("sqlite3 package not available. Exiting.")
    paths = [
        "mod_spatialite",
        "mod_spatialite.so",
        "/usr/lib/x86_64-linux-gnu/mod_spatialite.so",
        "/opt/homebrew/lib/mod_spatialite.dylib",
        "/usr/local/lib/mod_spatialite.dylib"
    ]
    for path in paths:
        try:
            conn = sqlite3.connect(":memory:")
            conn.enable_load_extension(True)
            conn.load_extension(path)
            conn.close()
            return path
        except sqlite3.OperationalError:
            continue
    raise RuntimeError("SpatiaLite extension not found.")

@pytest.fixture(scope="session")
def spatialite_url():
    """
    Creates a unique, shared in-memory SpatiaLite database URL per test.
    Keeps a dummy connection alive so the data survives connection closures.
    """
    if not sqlite3:
        raise RuntimeError("sqlite3 package not available. Exiting.")

    # Generate a unique memory space name for this test
    db_name = f"test_geo_{uuid.uuid4().hex}"
    
    # This URL string forces a persistent in-memory instance shared across connections
    url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"
    
    # Open a persistent low-level connection to boot up the DB and load SpatiaLite
    raw_url = f"file:{db_name}?mode=memory&cache=shared"
    keep_alive_conn = sqlite3.connect(raw_url, uri=True)
    keep_alive_conn.enable_load_extension(True)
    keep_alive_conn.load_extension(find_spatialite_extension())
    
    # Initialize the required OGC metadata tables once
    keep_alive_conn.execute("SELECT InitSpatialMetaData(1);")
    keep_alive_conn.commit()
    
    # Return the url for testing
    yield url
    
    # Closing this connection destroys the in-memory database after the test
    keep_alive_conn.close()

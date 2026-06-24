import pytest
from sqlalchemy import create_engine, text
from pytest_databases.docker.postgres import PostgresService

pytest_plugins = [
    "pytest_databases.docker.postgres",
]

@pytest.fixture(scope="session")
def postgres_image() -> str:
    return "postgis/postgis:16-3.4"

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


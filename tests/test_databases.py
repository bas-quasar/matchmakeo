from matchmakeo.databases import PostGISDatabase, SpatialiteDatabase

def test_postgis_url():
    db_name = "test_db"
    username = "test"
    password = "password"
    host = "localhost"
    port = 5432

    db = PostGISDatabase(
        database=db_name,
        username=username,
        password=password,
        host=host,
        port=port
    )

    dialect = "postgresql"
    driver = "psycopg"

    expected_str = f"{dialect}+{driver}://{username}:{password}@{host}:{port}/{db_name}"

    assert db.url == expected_str

def test_spatialite_url():

    filename="test_spatialite_db.sqlite"
    db = SpatialiteDatabase(
        filename=filename
    )

    dialect = "sqlite"

    expected_str = f"{dialect}:///{filename}"

    assert db.url == expected_str

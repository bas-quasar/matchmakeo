import datetime
import json
import os

from sqlalchemy import MetaData, Column, Table, Integer, DateTime, func
from geoalchemy2 import Geometry
import pytest

from matchmakeo import Query, Product



#
# Landsat ID	Wildfire ID	Time Difference	Expected Overlap %	Scenario
# 1	101	5 mins	80%	Near-instant match, high spatial overlap.
# 2	102	3.5 hours	30%	Multi-hour match, partial spatial overlap.
# 3	103	1.5 mins	5%	Instantaneous match, but very tiny edge clipping.
# 4	104	2 mins	0%	Fast temporal alignment, but absolutely no spatial match.
# 5	105	27 hours	100%

def _build_mock_product(db, fixtures_file, table_name, date_fields):
    """
    Generic helper to construct a dynamic table, insert JSON mock data,
    and return the metadata and Product instance for testing.
    """
    metadata = MetaData()
    
    columns = [
        Column("id", Integer, primary_key=True),
        Column("timestamp", DateTime, nullable=False),
        Column("geometry", Geometry("POLYGON", srid=4326), nullable=False)
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

@pytest.fixture(scope="function")
def product_a(database, filepath=os.path.join("tests", "fixtures", "dummy_product_a.json")):
    """Creates product table and populates it from JSON."""

    metadata, product = _build_mock_product(
        db=database,
        fixtures_file=filepath, 
        table_name="product_a", 
        date_fields=["timestamp"]
    )
    
    yield product
    metadata.drop_all(database.engine)

@pytest.fixture(scope="function")
def product_b(database, filepath=os.path.join("tests", "fixtures", "dummy_product_b.json")):
    """Creates product table and populates it from JSON."""

    metadata, product = _build_mock_product(
        db=database,
        fixtures_file=filepath, 
        table_name="product_b", 
        date_fields=["timestamp"]
    )
    
    yield product
    metadata.drop_all(database.engine)

class TestQuery:

    def test_query(
            self,
            database,
            product_a,
            product_b
            ):

        # initialisation with no products should raise an error
        with pytest.raises(ValueError):
            Query(database)

        # construct a query object    
        Query(database, product_a, product_b)

        # perform simple query
        in_time_range = Query(database, product_a).in_time_range(
            start_date=datetime.datetime.fromisoformat("2026-07-14T11:00:00"),
            end_date=datetime.datetime.fromisoformat("2026-07-14T12:00:00"),
            product=product_a,
        ).execute()
        assert len(in_time_range) == 5


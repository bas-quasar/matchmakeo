"""Integration tests to test downloading
"""

import json
import os
from unittest.mock import patch, Mock

import gportal
import pytest
from pytest_databases.docker.postgres import PostgresService
import sqlalchemy
from sqlalchemy.orm import Session

from matchmakeo.queryset import NasaCMRQueryset, EarthEngineQueryset, JaxaGportalQueryset
from matchmakeo.product import Product
from matchmakeo.catalogues import NasaCMR, Field, EarthEngine, JaxaGportal
from matchmakeo.databases import PostGISDatabase


@pytest.mark.slow # marked as slow because at present it performs an actual http request against jaxa gportal
def test_gportal(postgres_service: PostgresService):

    db = PostGISDatabase(
        database=postgres_service.database,
        username=postgres_service.user,
        password=postgres_service.password,
        host=postgres_service.host,
        port=postgres_service.port
    )

    queryset = JaxaGportalQueryset(
        start_date="2020-01-01",
        end_date="2020-01-31",
        lat_max=-70,
        lat_min=-90,
        lon_max=180,
        lon_min=-180,
    )
    product = Product(name="11001002", table="test_amsr")
    catalogue = JaxaGportal(
        username="test",
        password="password"
    )
    results = catalogue.download_footprints(product=product, queryset=queryset, database=None, dry_run=True)
    assert results.params["datasetId"] == product.name
    assert results.matched() > 0

    results = catalogue.download_footprints(product=product, queryset=queryset, database=db, dry_run=False)

@patch('gportal.search.Search.products')
@patch('gportal.search.Search.matched')
def test_mock_gportal(mock_search_matched, mock_search_products, postgres_service: PostgresService):

    db = PostGISDatabase(
        database=postgres_service.database,
        username=postgres_service.user,
        password=postgres_service.password,
        host=postgres_service.host,
        port=postgres_service.port
    )

    queryset = JaxaGportalQueryset(
        start_date="2020-01-01",
        end_date="2020-01-31",
        lat_max=-70,
        lat_min=-90,
        lon_max=180,
        lon_min=-180,
    )
    product = Product(name="11001002", table="test_amsr")
    catalogue = JaxaGportal(
        username="test",
        password="password"
    )

    # create the mock products response
    with open(os.path.join("tests", "fixtures", "gportal_products.json")) as fp:
        mock_products_geojson = json.load(fp)
    mock_products = [gportal.product.Product(geojson=p) for p in mock_products_geojson]

    # test dry run behaviour
    mock_search_matched.return_value = Mock()
    mock_search_matched.return_value = len(mock_products)

    results = catalogue.download_footprints(product=product, queryset=queryset, database=None, dry_run=True)
    assert results.params["datasetId"] == product.name
    assert results.matched() == len(mock_products)

    # test no products behaviour
    mock_search_products.return_value = Mock()
    mock_search_products.return_value = None
    results = catalogue.download_footprints(product=product, queryset=queryset, database=db, dry_run=False)
    assert results is None

    # test with mocked products
    def mock_products_generator():
        yield from mock_products
    mock_search_products.return_value = Mock()
    mock_search_products.side_effect = mock_products_generator

    results = catalogue.download_footprints(product=product, queryset=queryset, database=db, dry_run=False)

    metadata = sqlalchemy.MetaData()
    table = sqlalchemy.Table(product.table, metadata, autoload_with=db.engine)

    with Session(db.engine) as session:
        statement = sqlalchemy.select(table)
        rows = session.execute(statement).all()
        assert len(rows) == len(mock_products)
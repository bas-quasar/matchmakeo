"""Integration tests to test downloading
"""

import json
import os
import unittest
from unittest.mock import patch, Mock

import gportal
import pytest
from pytest_databases.docker.postgres import PostgresService
import requests_mock
import sqlalchemy
from sqlalchemy.orm import Session

from matchmakeo.queryset import NasaCMRQueryset, EarthEngineQueryset, JaxaGportalQueryset
from matchmakeo.product import Product
from matchmakeo.catalogues import NasaCMR, Field, EarthEngine, JaxaGportal
from matchmakeo.databases import PostGISDatabase


@pytest.fixture(scope="module")
def database(postgres_service: PostgresService):

    yield PostGISDatabase(
        database=postgres_service.database,
        username=postgres_service.user,
        password=postgres_service.password,
        host=postgres_service.host,
        port=postgres_service.port
    )

class TestNasaCmr:

    @pytest.fixture
    def queryset(self):
        yield NasaCMRQueryset(
            start_date="2020-01-01",
            end_date="2020-01-31",
            lat_max=-70,
            lat_min=-90,
            lon_max=180,
            lon_min=-180,
        )

    @pytest.fixture
    def product(self):
        yield Product(name="MOD021KM", table="test_modis_aqua")

    @pytest.fixture
    def catalogue(self):
        yield NasaCMR(
            client_id="test_matchmakeo",
            url="https://cmr.earthdata.nasa.gov/search/granules.json",
            )
        
    @pytest.fixture
    def mock_cmr_products(self):
        with open(os.path.join("tests", "fixtures", "nasa_cmr_results.json"), "r") as f:
            results = json.load(f)
        yield results

    def test_mock_cmr(
        self,
        database,
        queryset,
        product,
        catalogue,
        mock_cmr_products,
        ):
        
        with requests_mock.Mocker() as m:
            m.get(catalogue.url,
                  status_code=200,
                  json=mock_cmr_products
                  )
            catalogue.download_footprints(product=product, queryset=queryset, database=database, dry_run=False)

        metadata = sqlalchemy.MetaData()
        table = sqlalchemy.Table(product.table, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()
            assert len(rows) == len(mock_cmr_products["feed"]["entry"])

class TestJaxaGportal:

    @pytest.fixture
    def queryset(self):
        yield JaxaGportalQueryset(
            start_date="2020-01-01",
            end_date="2020-01-31",
            lat_max=-70,
            lat_min=-90,
            lon_max=180,
            lon_min=-180,
        )

    @pytest.fixture
    def product(self):
        yield Product(name="11001002", table="test_amsr")

    @pytest.fixture
    def catalogue(self):
        yield JaxaGportal(
            username="test",
            password="password"
        )

    @patch('gportal.search.Search.products')
    @patch('gportal.search.Search.matched')
    def test_mock_gportal(
        self,
        mock_search_matched,
        mock_search_products,
        database,
        queryset,
        product,
        catalogue,
        ):

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
        results = catalogue.download_footprints(product=product, queryset=queryset, database=database, dry_run=False)
        assert results is None

        # test with mocked products
        def mock_products_generator():
            yield from mock_products
        mock_search_products.return_value = Mock()
        mock_search_products.side_effect = mock_products_generator

        results = catalogue.download_footprints(product=product, queryset=queryset, database=database, dry_run=False)

        metadata = sqlalchemy.MetaData()
        table = sqlalchemy.Table(product.table, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()
            assert len(rows) == len(mock_products)

    @pytest.mark.skip(reason="performs an actual http request, skipped for automated testing, preserved for occasional manual testing.")
    def test_live_gportal(
        self,
        database,
        queryset,
        product,
        catalogue,
        ):

        results = catalogue.download_footprints(product=product, queryset=queryset, database=None, dry_run=True)
        assert results.params["datasetId"] == product.name
        num_results = results.matched()
        assert num_results > 0

        results = catalogue.download_footprints(product=product, queryset=queryset, database=database, dry_run=False)

        metadata = sqlalchemy.MetaData()
        table = sqlalchemy.Table(product.table, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()
            assert len(rows) == num_results


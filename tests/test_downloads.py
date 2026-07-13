"""Integration tests for downloading
"""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch, Mock, MagicMock

import gportal
import pytest
from pytest_databases.docker.postgres import PostgresService
import requests_mock
import sqlalchemy
from sqlalchemy.orm import Session

from matchmakeo.queryset import NasaCMRQueryset, EarthEngineQueryset, JaxaGportalQueryset
from matchmakeo.product import Product
from matchmakeo.catalogues import NasaCMR, Field, EarthEngine, JaxaGportal
from matchmakeo.databases import PostGISDatabase, SpatialiteDatabase

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
        yield Product(name="MOD021KM", table_name="test_modis_aqua")

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
        table = sqlalchemy.Table(product.table_name, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()
            assert len(rows) == len(mock_cmr_products["feed"]["entry"])

    @pytest.mark.skip(reason="Performs requests against the live catalogue, skipped for automated testing, preserved for occasional manual testing.")
    def test_live_cmr(
        self,
        database,
        queryset,
        product,
        catalogue,
        mock_cmr_products,
        ):
        
        catalogue.download_footprints(product=product, queryset=queryset, database=database, dry_run=False)

        metadata = sqlalchemy.MetaData()
        table = sqlalchemy.Table(product.table_name, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()

class TestEarthEngine:

    @pytest.fixture
    def queryset(self):
        yield EarthEngineQueryset(
            start_date="2020-01-01",
            end_date="2020-01-02",
            lat_max=-70,
            lat_min=-90,
            lon_max=180,
            lon_min=-180,
        )

    @pytest.fixture
    def product(self):
        yield Product(
            name='COPERNICUS/S2_HARMONIZED',
            table_name="s2",
        )

    @pytest.fixture
    def mock_num_workers(self, monkeypatch):
        monkeypatch.setenv("NUM_WORKERS", "1")
        
    @patch('matchmakeo.catalogues.ee')
    def test_mock_earthengine(
            self,
            mock_ee,
            mock_num_workers,
            database,
            queryset,
            product,
            ):

        with open(os.path.join("tests", "fixtures", "earthengine_results.json"), "r") as f:
            mock_info_features = json.load(f)
        mock_info_response = {"features": mock_info_features}
        
        # Configure the chain to return our fake data when getInfo() is called
        mock_feature_collection = MagicMock()
        # mock_selected_collection = MagicMock() # we aren't using .select yet
        
        mock_ee.FeatureCollection.return_value = mock_feature_collection
        # mock_feature_collection.select.return_value = mock_selected_collection
        mock_feature_collection.getInfo.return_value = mock_info_response

        catalogue = EarthEngine(
            project_id="matchmakeo",
            service_account=True,
            )

        catalogue.download_footprints(
            product=product,    
            queryset=queryset,
            database=database,
            dry_run=False,
        )

        mock_ee.ImageCollection.assert_called_with(product.name)

        metadata = sqlalchemy.MetaData()
        table = sqlalchemy.Table(product.table_name, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()
            assert len(rows) == len(mock_info_features)

    @pytest.mark.skip(reason="Performs requests against the live catalogue, skipped for automated testing, preserved for occasional manual testing.")
    def test_live_earthengine(
            self,
            mock_num_workers,
            database,
            queryset,
            product,
            ):

        catalogue = EarthEngine(
            project_id="matchmakeo",
            service_account=True,
            )

        catalogue.download_footprints(
            product=product,
            queryset=queryset,
            database=database,
            dry_run=False,
        )

        metadata = sqlalchemy.MetaData()
        table = sqlalchemy.Table(product.table_name, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()

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
        yield Product(name="11001002", table_name="test_amsr")

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
        table = sqlalchemy.Table(product.table_name, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()
            assert len(rows) == len(mock_products)

    @pytest.mark.skip(reason="Performs requests against the live catalogue, skipped for automated testing, preserved for occasional manual testing.")
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
        table = sqlalchemy.Table(product.table_name, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()
            assert len(rows) == num_results


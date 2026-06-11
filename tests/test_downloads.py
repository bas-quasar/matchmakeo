"""Integration tests to test downloading
TODO: mocking
"""

import pytest
from pytest_databases.docker.postgres import PostgresService

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
    catalogue = JaxaGportal()
    results = catalogue.download_footprints(product=product, queryset=queryset, database=None, dry_run=True)
    assert results.params["datasetId"] == product.name
    assert results.matched() > 0

    results = catalogue.download_footprints(product=product, queryset=queryset, database=db, dry_run=False)
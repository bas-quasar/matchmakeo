import unittest

import pytest
from pytest_databases.docker.postgres import PostgresService

from matchmakeo.catalogues import NasaCMR
from matchmakeo.databases import PostGISDatabase
from matchmakeo.product import Product
from matchmakeo.queryset import Queryset

def test_queryset_type_warning(postgres_service: PostgresService):
    """Test that using the wrong queryset type for the catalogue results in a warning."""
    
    queryset = Queryset(
        start_date="2025-01-01",
        end_date="2025-01-02"
    )
    product = Product(
        name="test",
        table="test_table"
    )
    catalogue = NasaCMR()
    database = PostGISDatabase(
        username=postgres_service.user,
        password=postgres_service.password,
        host=postgres_service.host,
        port=postgres_service.port,
        database=postgres_service.database,
    )
    
    with pytest.warns(UserWarning):
        catalogue._check_queryset_type(queryset)

def test_nasa_cmr_bounding_box_str():
    "Test that bounding box string gives the correct order of coordinates, as expected by cmr."
    
    queryset = Queryset(
        start_date="2025-01-01",
        end_date="2025-01-02",
    )
    catalogue = NasaCMR()

    assert catalogue._get_bounding_box(queryset) == "-180, -90, 180, 90"

    queryset.lon_min = 0
    queryset.lon_max = -120
    queryset.lat_min = 0
    queryset.lat_max = +20

    assert catalogue._get_bounding_box(queryset) == "-120, 0, 0, 20"

    queryset.lon_min = 0
    queryset.lon_max = 0
    queryset.lat_min = 0
    queryset.lat_max = 0

    assert catalogue._get_bounding_box(queryset) == "0, 0, 0, 0"

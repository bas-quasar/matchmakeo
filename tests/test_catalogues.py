import pytest
from pytest_databases.docker.postgres import PostgresService

from matchmakeo.catalogues import NasaCMR
from matchmakeo.databases import PostGISDatabase
from matchmakeo.download_params import DownloadParams
from matchmakeo.product import Product


def test_download_params_type_warning(postgres_service: PostgresService):
    """Test that using the wrong download_params type for the catalogue results in a warning."""

    download_params = DownloadParams(start_date="2025-01-01", end_date="2025-01-02")
    Product(name="test", table_name="test_table")
    catalogue = NasaCMR()
    PostGISDatabase(
        username=postgres_service.user,
        password=postgres_service.password,
        host=postgres_service.host,
        port=postgres_service.port,
        database=postgres_service.database,
    )

    with pytest.warns(UserWarning):
        catalogue._check_download_params_type(download_params)


def test_nasa_cmr_bounding_box_str():
    "Test that bounding box string gives the correct order of coordinates, as expected by cmr."

    download_params = DownloadParams(
        start_date="2025-01-01",
        end_date="2025-01-02",
    )
    catalogue = NasaCMR()

    assert catalogue._get_bounding_box(download_params) == "-180,-90,180,90"

    download_params.lon_min = 0
    download_params.lon_max = -120
    download_params.lat_min = 0
    download_params.lat_max = +20

    assert catalogue._get_bounding_box(download_params) == "-120,0,0,20"

    download_params.lon_min = 0
    download_params.lon_max = 0
    download_params.lat_min = 0
    download_params.lat_max = 0

    assert catalogue._get_bounding_box(download_params) == "0,0,0,0"

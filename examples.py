"Example downloads including MODIS footprints."

from pathlib import Path

from sqlalchemy import String

from matchmakeo.queryset import NasaCMRQueryset, EarthEngineQueryset
from matchmakeo.product import Product
from matchmakeo.catalogues import NasaCMR, Field, EarthEngine
from matchmakeo.databases import PostGISDatabase

# create a database object
# create a catalogue object
# create dataset and query object
# run the download
# 

database = PostGISDatabase(
    username="postgres",
    password="password",
    database="matchmakeo",
    host="localhost",
    port=5432,
)

catalogue = NasaCMR(
    client_id="test_BAS",
    url="https://cmr.earthdata.nasa.gov/search/granules.json"#"https://cmr.sit.earthdata.nasa.gov/search/granules.json"
)

queryset = NasaCMRQueryset(
    start_date="2020-01-01",
    end_date="2020-01-31",
    page_size=200,
    lat_max=-70,
    lat_min=-90,
    lon_max=180,
    lon_min=-180,
)

product = Product(
    name="MOD021KM",#  MOD021KM - terra (original download in ~April) /  Use MYD021KM - Aqua (new download in May)
    # data_dir=Path("./data/modis_aqua"),
    table="modis_aqua",
)

catalogue.download_footprints(
    product=product,
    queryset=queryset,
    database=database,
    dry_run=True
)

# catalogue = EarthEngine()

# queryset = EarthEngineQueryset(
#     start_date="2020-01-01",
#     end_date="2020-01-02",
#     lat_max=-70,
#     lat_min=-90,
#     lon_max=180,
#     lon_min=-180,
# )

# product = Product(
#     name='COPERNICUS/S2_HARMONIZED',
#     table="s2",
# )

# catalogue.download_footprints(
#     product=product,
#     queryset=queryset,
#     database=database,
#     project_name="quasar-test-460510",
#     # dry_run=True,
# )
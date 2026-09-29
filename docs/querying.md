# Querying

Once we have copies of the metadata we want in our database, we can then perform more fine grained queries which can include combined querying across multiple products.

## Single products

```py
# assuming we have run catalogue.download_footprints() to download metadata into our database

from matchmakeo import Product, Query
from matchmakeo.databases import PostGISDatabase

# you don't need to run this in the same session as your footprint download

database = PostGISDatabase(
    username="postgres",
    password="password",
    database="matchmakeo",
    host="localhost",
    port=5432,
)

# but define the same product object as you used for the download(s)
product = Product(
    name="MOD021KM",
    table_name="modis_aqua",
)

# construct and execute a simple bounding box query
results = (  # use brackets to separate a long query across multiple lines
    Query(database, product)
    .within_bbox(
        min_x=0.077591,
        min_y=52.169931,
        max_x=0.190887,
        max_y=52.233477,
        srid=4326,
    )
    .execute()
)

# for single products, Query.execute() returns a matchmakeo.ResultSet object
# which can be used to return the results in a few different formats

len(results)  # returns the number of results
results.get_ids()  # returns a list of the ids of matching images
results.to_dicts()  # returns a list of dictionaries, each one representing one image and its metadata
```

## Multiple products

### Simple queries
The single product queries can also be used with queries composed of multiple products, e.g.

```py
# imagine we have a product_a and a product_b

results = Query(database, product_a, product_b).within_bbox(...).execute()
```

### Join/intersection queries
Things get interesting when we query depending on intersections across multiple products, for example

```py
import datetime

results = (
    Query(database, product_a, product_b)
    .where_spatiotemporal_match(
        product_a,
        product_b,
        relative_to=product_a,  # the product which the overlap fraction is measured against
        min_overlap_fraction=0.1,  # the minimum fraction of the `relative_to` product which is covered by the other product
        max_time_delta=datetime.timedelta(
            days=2
        ),  # the time difference allowed between overlapping pairs
    )
    .execute()
)

# results for more than one product are MatchResultSet objects
# they have the same methods as ResultSet, such as get_ids()
results.get_ids()

# but .to_dicts() returns a list of dicts containing dictionaries each representing a single metadata product
results.to_dicts()
```

## Chaining queries

Each query method can be chained with others, with the first being the first to be evaluated, for example:

```py
results = (
    Query(database, product_a, product_b)
    .within_bbox(...)
    .where_spatiotemporal_match(...)
    .execute()
)
```
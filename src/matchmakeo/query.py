from abc import ABC
from datetime import datetime, timedelta

import shapely
from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_MakeEnvelope
from sqlalchemy import Column, Table, func
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Bundle, Session
from sqlalchemy.sql.expression import FunctionElement
from sqlalchemy.types import Float

from .databases import Database
from .product import Product
from .utils import setUpLogging

log = setUpLogging(__name__)


class Query:
    """Constructor for all database product queries.
    Queries can be chained together on the query object, e.g. Query().intersects_bbox().with_parameter_equal()
    and must be executed with .execute, e.g. Query().intersects_bbox().with_parameter_equal().execute()
    """

    def __init__(self, database: Database, *products):
        """
        Initializes the query/match engine using one or more Product instances.
        """
        if not products:
            raise ValueError("Query requires at least one Product.")

        self._database = database
        self._connection = self._database.connect()
        self._session = Session(bind=self._connection)
        self.products = products

        self.tables = []
        self._product_to_alias = {}
        self._bundles = []

        for idx, p in enumerate(products):
            # Alias the table to avoid name collisions on self-joins
            aliased_table = p.get_table(self._database).alias(f"t{idx}")
            self.tables.append(aliased_table)
            self._product_to_alias[p] = aliased_table

            # Bundle the table's columns together into a named group
            # This prevents SQLAlchemy from flattening all columns into one row
            bundle = Bundle(f"product_{idx}", *aliased_table.c)
            self._bundles.append(bundle)

        # Initialize the query with all target tables
        self._query = self._session.query(*self._bundles)

        # Explicit spatial join setup
        if len(self.tables) > 1:
            self._query = self._query.select_from(self.tables[0])
            for i in range(1, len(self.tables)):
                prev_geom = self.tables[i - 1].c[self.products[i - 1].geometry_column]
                curr_geom = self.tables[i].c[self.products[i].geometry_column]
                self._query = self._query.join(
                    self.tables[i],
                    prev_geom.ST_Intersects(
                        curr_geom, use_spatial_index=False
                    ),  # for spatialite, Pass use_spatial_index=False Prevents GeoAlchemy2 from referencing the unaliased base table's rowid
                )

    def _get_table_obj(self, product=None):
        """
        Fetches the cached aliased table object corresponding to a given Product instance.

        If product is None and only a single Product was registered, defaults
        to the single table.
        """
        if product is None:
            if len(self.products) == 1:
                return self.tables[0]
            raise ValueError(
                "You must specify which Product to filter when matching multiple products."
            )

        if product not in self._product_to_alias:
            raise ValueError(
                f"Product '{product}' was not provided during query initialization."
            )

        return self._product_to_alias[product]

    def _resolve_products(self, product=None):
        """
        Normalizes the target product input into a list of Product instances.
        Defaults to all registered products if product is None.
        """
        if product is None:
            return list(self.products)
        if isinstance(product, (list, tuple, set)):
            return list(product)
        return [product]

    # ==========================================
    # SINGLE & MULTI-PRODUCT FILTERS
    # ==========================================

    def in_time_range(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        product: Product | None = None,
        time_attr="timestamp",
    ):
        """
        Filters records occurring within [start_time, end_time].

        Args:
            start_time: Start datetime (inclusive), or None.
            end_time: End datetime (inclusive), or None.
            product: Product, list of Products, or None (defaults to all products).
            time_attr: Column name string, or dict mapping {product: "col_name"}.

        Returns:
            Query: The updated `Query` instance for method chaining.
        """
        target_products = self._resolve_products(product)
        conditions = []

        for p in target_products:
            table = self._get_table_obj(p)

            # Resolve column name if passed as a dictionary mapping
            col_name = (
                time_attr.get(p, "timestamp")
                if isinstance(time_attr, dict)
                else time_attr
            )
            time_col = getattr(table.c, col_name)

            if start_time is not None:
                conditions.append(time_col >= start_time)
            if end_time is not None:
                conditions.append(time_col <= end_time)

        if conditions:
            self._query = self._query.filter(*conditions)

        return self

    def intersects_bbox(
        self,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        srid: int = 4326,
        product: Product | None = None,
    ):
        """
        Filters records whose geometry intersects the bounding envelope [xmin, ymin, xmax, ymax].

        Args:
            xmin, ymin, xmax, ymax (float): Bounding box spatial coordinates.
            srid (int): Spatial Reference System Identifier (default 4326).
            product (Product|list|None): Product, list of Products, or None (defaults to all products).

        Returns:
            Query: The updated `Query` instance for method chaining.

        """
        target_products = self._resolve_products(product)
        envelope = func.ST_MakeEnvelope(xmin, ymin, xmax, ymax, srid)

        conditions = []
        for p in target_products:
            table = self._get_table_obj(p)
            geom_col = table.c[p.geometry_column]
            conditions.append(geom_col.ST_Intersects(envelope, use_spatial_index=False))

        if conditions:
            self._query = self._query.filter(*conditions)

        return self

    def with_param_equal(self, params: dict, product: Product | None = None):
        """Filters products with a parameter value equal to the value specified.

        Args:
            params (dict): keys are column names, values the value to be filtered against.
            product (Product | None, optional): list of Products, or None (defaults to all products).

        Returns:
            Query: The updated `Query` instance for method chaining.

        """
        target_products = self._resolve_products(product)

        conditions = []
        for p in target_products:
            table = self._get_table_obj(p)
            for k, v in params.items():
                col = table.c[k]
                conditions.append(col == v)

        if conditions:
            self._query = self._query.filter(*conditions)

        return self

    def with_param_gt(self, params: dict, product: Product | None = None):
        """Filters products with a parameter value greater than (>) the value specified.

        Args:
            params (dict): keys are column names, values the value to be filtered against.
            product (Product | None, optional): list of Products, or None (defaults to all products).

        Returns:
            Query: The updated `Query` instance for method chaining.

        Raises:
            ValueError: If products not specified when Query contains more than 2 products; if only one product is specified; if min_overlap_fraction is not between 0 & 1.
        """
        target_products = self._resolve_products(product)

        conditions = []
        for p in target_products:
            table = self._get_table_obj(p)
            for k, v in params.items():
                col = table.c[k]
                conditions.append(col > v)

        if conditions:
            self._query = self._query.filter(*conditions)

        return self

    def with_param_ge(self, params: dict, product: Product | None = None):
        """Filters products with a parameter value greater than or equal to (>=) the value specified.

        Args:
            params (dict): keys are column names, values the value to be filtered against.
            product (Product | None, optional): list of Products, or None (defaults to all products).

        Returns:
            Query: The updated `Query` instance for method chaining.
        """
        target_products = self._resolve_products(product)

        conditions = []
        for p in target_products:
            table = self._get_table_obj(p)
            for k, v in params.items():
                col = table.c[k]
                conditions.append(col >= v)

        if conditions:
            self._query = self._query.filter(*conditions)

        return self

    def with_param_lt(self, params: dict, product: Product | None = None):
        """Filters products with a parameter value less than (<) the value specified.

        Args:
            params (dict): keys are column names, values the value to be filtered against.
            product (Product | None, optional): list of Products, or None (defaults to all products).


        Returns:
            Query: The updated `Query` instance for method chaining.
        """
        target_products = self._resolve_products(product)

        conditions = []
        for p in target_products:
            table = self._get_table_obj(p)
            for k, v in params.items():
                col = table.c[k]
                conditions.append(col < v)

        if conditions:
            self._query = self._query.filter(*conditions)

        return self

    def with_param_le(self, params: dict, product: Product | None = None):
        """Filters products with a parameter value less than or equal to (<=) the value specified.

        Args:
            params (dict): keys are column names, values the value to be filtered against.
            product (Product | None, optional): list of Products, or None (defaults to all products).

        Returns:
            Query: The updated `Query` instance for method chaining.
        """
        target_products = self._resolve_products(product)

        conditions = []
        for p in target_products:
            table = self._get_table_obj(p)
            for k, v in params.items():
                col = table.c[k]
                conditions.append(col <= v)

        if conditions:
            self._query = self._query.filter(*conditions)

        return self

    def intersects_polygon(
        self,
        polygon: shapely.Polygon | str,
        product: Product | None = None,
        srid: int | None = None,
    ):
        """
        Filters query records to those whose geometry intersects a given polygon.

        Accepts either a Shapely `Polygon` instance or a WKT string. Handles
        SRID resolution across inputs and wraps the geometry into a dialect-aware
        GeoAlchemy2 element to maintain cross-database compatibility (PostGIS and SpatiaLite).

        Args:
            polygon: A Shapely `Polygon` object or a WKT string representing
                the target spatial boundary.
            product: Target `Product` instance, sequence of `Product`s, or `None`.
                If `None`, the filter is applied across all products registered in
                the query. Defaults to `None`.
            srid: Spatial Reference System Identifier (e.g., 4326). Required if
                `polygon` is a raw WKT string or lacks an embedded SRID. Defaults to `None`.

        Returns:
            Query: The updated `Query` instance for method chaining.

        Raises:
            TypeError: If `polygon` is neither a `shapely.Polygon` nor a `str`.
            ValueError: If an SRID cannot be resolved from either `polygon` or the
                `srid` parameter.
        """

        target_products = self._resolve_products(product)

        if isinstance(polygon, str):
            log.info(
                "Got str type polygon, assuming WKT format and converting to shapely.Polygon"
            )
            polygon = shapely.from_wkt(polygon)
        elif not isinstance(polygon, shapely.Polygon):
            raise TypeError(
                f"Polygon of type str or shapely.Polygon are supported, got {type(polygon)}."
            )

        # Resolve SRID cleanly
        polygon_srid = int(shapely.get_srid(polygon))

        if srid is None and polygon_srid == 0:
            raise ValueError(
                f"SRID must either be set on the supplied polygon or passed as an argument, got {srid=} and {polygon_srid=}"
            )
        elif srid is not None and polygon_srid != 0 and srid != polygon_srid:
            log.warning(
                f"Set SRID both as an argument ({srid}) and in the supplied polygon ({polygon_srid}). Using polygon SRID ({polygon_srid})."
            )
            effective_srid = polygon_srid
        else:
            effective_srid = polygon_srid if polygon_srid != 0 else srid

        #  Wrap WKT in GeoAlchemy2's WKTElement with explicit SRID
        wkt_element = WKTElement(shapely.to_wkt(polygon), srid=effective_srid)

        # Construct spatial intersection filter
        conditions = []
        for p in target_products:
            table = self._get_table_obj(p)
            geom_col = table.c[p.geometry_column]
            conditions.append(
                geom_col.ST_Intersects(wkt_element, use_spatial_index=False)
            )

        if conditions:
            self._query = self._query.filter(*conditions)

        return self

    def intersects_path(self):
        raise NotImplementedError

    # ==========================================
    # PAIRWISE CROSS-TABLE JOIN FILTERS
    # ==========================================

    def where_spatial_overlap(
        self,
        relative_to: Product,
        min_overlap_fraction: float,
        product_y: Product | None = None,
        product_x: Product | None = None,
    ):
        """
        Filters pairs of records between two products where spatial overlap fraction exceeds min_overlap_fraction (0.0 to 1.0).

        Args:
            product_x: First Product instance (defaults to self.products[0] if Query has 2 products).
            product_y: Second Product instance (defaults to self.products[1] if Query has 2 products).
            min_overlap_fraction: Minimum spatial overlap ratio (e.g., 0.25 for 25%).
            relative_to: Area denominator: 'first', 'second', 'union', or 'min'.

        Returns:
            Query: The updated `Query` instance for method chaining.

        Raises:
            ValueError: If products not specified when Query contains more than 2 products; if only one product is specified; if min_overlap_fraction is not between 0 & 1.
        """
        # Infer products when Query has exactly 2 products
        if product_x is None and product_y is None:
            if len(self.products) == 2:
                product_x, product_y = self.products[0], self.products[1]
            else:
                raise ValueError(
                    "You must specify product_x and product_y when Query contains more than 2 products."
                )
        elif product_x is None or product_y is None:
            raise ValueError(
                "Both product_x and product_y must be provided if specifying one."
            )

        if not (0.0 <= min_overlap_fraction <= 1.0):
            raise ValueError("min_overlap_fraction must be between 0.0 and 1.0")

        table_x = self._get_table_obj(product_x)
        table_y = self._get_table_obj(product_y)

        area_x = func.ST_Area(table_x.c[product_x.geometry_column])
        area_y = func.ST_Area(table_y.c[product_y.geometry_column])
        intersection_area = func.ST_Area(
            func.ST_Intersection(
                table_x.c[product_x.geometry_column],
                table_y.c[product_y.geometry_column],
            )
        )

        if relative_to == product_x:
            base_area = area_x
        elif relative_to == product_y:
            base_area = area_y
        # elif relative_to == "union":
        #     base_area = func.ST_Area(func.ST_Union(table_x.c.geom, table_y.c.geom))
        # elif relative_to == "min":
        #     # Normalizes against whichever polygon is smaller
        #     base_area = ScalarMin(area_x, area_y)
        else:
            raise ValueError("relative_to must be one of product_x or product_y")

        overlap_fraction = intersection_area / func.nullif(base_area, 0)

        # apply filter to query
        self._query = self._query.filter(
            overlap_fraction >= min_overlap_fraction,
        )

        return self

    def where_time_within(
        self,
        max_time_delta: float | timedelta,
        product_x: Product | None = None,
        product_y: Product | None = None,
        time_attr_x: str = "timestamp",
        time_attr_y: str = "timestamp",
    ):
        """
        Filters paired records to those occurring within `max_time_delta` of each other.

        Args:
            max_time_delta: Maximum time difference in seconds (float/int) or a timedelta object.
            product_x: First Product instance (defaults to self.products[0] if Query has 2 products).
            product_y: Second Product instance (defaults to self.products[1] if Query has 2 products).
            time_attr_x: Timestamp column name for product_x.
            time_attr_y: Timestamp column name for product_y.

        Returns:
            Query: The updated `Query` instance for method chaining.

        Raises:
            ValueError: If products not specified when Query contains more than 2 products; if only one product is specified.

        """
        # Infer products when Query has exactly 2 products
        if product_x is None and product_y is None:
            if len(self.products) == 2:
                product_x, product_y = self.products[0], self.products[1]
            else:
                raise ValueError(
                    "You must specify product_x and product_y when Query contains more than 2 products."
                )
        elif product_x is None or product_y is None:
            raise ValueError(
                "Both product_x and product_y must be provided if specifying one."
            )

        # Extract aliased table objects and timestamp columns
        table_x = self._get_table_obj(product_x)
        table_y = self._get_table_obj(product_y)

        time_x = table_x.c[time_attr_x]
        time_y = table_y.c[time_attr_y]

        # Standardize max_time_delta to seconds
        if isinstance(max_time_delta, timedelta):
            delta_seconds = max_time_delta.total_seconds()
        else:
            delta_seconds = float(max_time_delta)

        # Apply cross-dialect temporal filter
        self._query = self._query.filter(
            TimeDiffSeconds(time_x, time_y) <= delta_seconds
        )

        return self

    def where_spatiotemporal_match(
        self,
        relative_to: Product,
        min_overlap_fraction: float,
        max_time_delta: timedelta | float,
        product_x: Product | None = None,
        product_y: Product | None = None,
        time_column_x: str = "timestamp",
        time_column_y: str = "timestamp",
    ):
        """
        Filters pairs of records between two products where:
        1. Spatial overlap fraction exceeds min_overlap_fraction (0.0 to 1.0).
        2. Absolute difference between specified timestamp columns is within max_time_delta.

        Args:
            relative_to: must be one of the products in self.products
            min_overlap_fraction: Minimum spatial overlap ratio (e.g., 0.25 for 25%).
            max_time_delta: Max time difference as a datetime.timedelta or number of seconds.
            product_x: First Product instance (defaults to self.products[0] if Query has 2 products).
            product_y: Second Product instance (defaults to self.products[1] if Query has 2 products).
            time_column_x: Name of timestamp column on product_x.
            time_column_y: Name of timestamp column on product_y.

        Returns:
            Query: The updated `Query` instance for method chaining.

        Raises:
            ValueError: If products not specified when Query contains more than 2 products; if only one product is specified; if min_overlap_fraction is not between 0 & 1.

        """
        # Infer products when Query has exactly 2 products
        if product_x is None and product_y is None:
            if len(self.products) == 2:
                product_x, product_y = self.products[0], self.products[1]
            else:
                raise ValueError(
                    "You must specify product_x and product_y when Query contains more than 2 products."
                )
        elif product_x is None or product_y is None:
            raise ValueError(
                "Both product_x and product_y must be provided if specifying one."
            )

        if not (0.0 <= min_overlap_fraction <= 1.0):
            raise ValueError("min_overlap_fraction must be between 0.0 and 1.0")

        table_x = self._get_table_obj(product_x)
        table_y = self._get_table_obj(product_y)

        # -------------------------------------------------------------
        # SPATIAL OVERLAP FRACTION FILTER
        # -------------------------------------------------------------
        area_x = func.ST_Area(table_x.c[product_x.geometry_column])
        area_y = func.ST_Area(table_y.c[product_y.geometry_column])
        intersection_area = func.ST_Area(
            func.ST_Intersection(
                table_x.c[product_x.geometry_column],
                table_y.c[product_y.geometry_column],
            )
        )

        if relative_to == product_x:
            base_area = area_x
        elif relative_to == product_y:
            base_area = area_y
        # elif relative_to == "union":
        #     base_area = func.ST_Area(func.ST_Union(table_x.c.geom, table_y.c.geom))
        # elif relative_to == "min":
        #     # Normalizes against whichever polygon is smaller
        #     base_area = ScalarMin(area_x, area_y)
        else:
            raise ValueError("relative_to must be one of product_x or product_y")

        overlap_fraction = intersection_area / func.nullif(base_area, 0)

        # Standardize delta to seconds float
        if isinstance(max_time_delta, timedelta):
            delta_seconds = max_time_delta.total_seconds()
        elif isinstance(max_time_delta, (int, float)):
            delta_seconds = float(max_time_delta)
        else:
            raise TypeError(
                "max_time_delta must be a datetime.timedelta or a number of seconds."
            )

        time_x = getattr(table_x.c, time_column_x)
        time_y = getattr(table_y.c, time_column_y)

        # Compute absolute time difference in seconds dynamically
        temporal_condition = TimeDiffSeconds(time_x, time_y) <= delta_seconds

        # -------------------------------------------------------------
        # APPLY FILTERS TO QUERY
        # -------------------------------------------------------------
        self._query = self._query.filter(
            overlap_fraction >= min_overlap_fraction, temporal_condition
        )

        return self

    # ==========================================
    # Query execution
    # ==========================================

    def execute(self):
        """Executes the query and yields the resulting data rows.

        Returns:
            ResultSet or MatchResultSet
        """
        try:
            results = self._query.all()

            if len(self.products) == 1:
                return ResultSet(results, self.products[0])

            return MatchResultSet(results, *self.products)

        finally:
            self._session.close()
            self._connection.close()


### Spatial function mapping from PostGIS to Spatialite


# Map directly to GeoAlchemy2's built-in ST_MakeEnvelope class
@compiles(ST_MakeEnvelope, "sqlite")
def compile_makeenvelope_sqlite(element, compiler, **kw):
    args = list(element.clauses)

    if len(args) == 5:
        return f"SetSRID(BuildMbr({compiler.process(args[0], **kw)}, {compiler.process(args[1], **kw)}, {compiler.process(args[2], **kw)}, {compiler.process(args[3], **kw)}), {compiler.process(args[4], **kw)})"
    elif len(args) == 4:
        return f"BuildMbr({compiler.process(args[0], **kw)}, {compiler.process(args[1], **kw)}, {compiler.process(args[2], **kw)}, {compiler.process(args[3], **kw)})"
    else:
        raise ValueError("ST_MakeEnvelope requires 4 or 5 arguments.")


class TimeDiffSeconds(FunctionElement):
    """Calculates abs(time1 - time2) in seconds across dialects."""

    type = Float()
    name = "time_diff_seconds"


@compiles(TimeDiffSeconds, "postgresql")
def _time_diff_postgresql(element, compiler, **kw):
    arg1, arg2 = list(element.clauses)
    return f"ABS(EXTRACT(EPOCH FROM ({compiler.process(arg1)} - {compiler.process(arg2)})))"


@compiles(TimeDiffSeconds, "sqlite")
def _time_diff_sqlite(element, compiler, **kw):
    arg1, arg2 = list(element.clauses)
    # julianday converts ISO strings to days; multiply by 86400 to get seconds
    return f"ABS((julianday({compiler.process(arg1)}) - julianday({compiler.process(arg2)})) * 86400.0)"


class ScalarMin(FunctionElement):
    """Calculates min(a, b) across dialects for relative_to='min'."""

    type = Float()
    name = "scalar_min"


@compiles(ScalarMin, "postgresql")
def _scalar_min_pg(element, compiler, **kw):
    arg1, arg2 = list(element.clauses)
    return f"LEAST({compiler.process(arg1)}, {compiler.process(arg2)})"


@compiles(ScalarMin, "sqlite")
def _scalar_min_sqlite(element, compiler, **kw):
    arg1, arg2 = list(element.clauses)
    return f"MIN({compiler.process(arg1)}, {compiler.process(arg2)})"


class ResultBase(ABC):
    def __iter__(self):
        return iter(self.raw_results)

    def __len__(self):
        return len(self.raw_results)


class ResultSet(ResultBase):
    """Wraps the results of a single-product query."""

    def __init__(self, raw_results, product):
        self.raw_results = raw_results
        self.product = product

    def get_ids(self, id_col="id"):
        return [getattr(row[0]._mapping, id_col) for row in self.raw_results]

    def to_dicts(self):
        return [dict(row[0]._mapping) for row in self.raw_results]


class MatchResultSet(ResultBase):
    """Wraps the paired/grouped results of an N-product Query."""

    def __init__(self, raw_results, *products):
        self.raw_results = raw_results
        self.products = products

    def get_ids(self, product_index: int, id_col="id"):
        """
        Returns a list of IDs for a specific product in the match group,
        identified by its index (0 for the first product, 1 for the second, etc.)
        """
        if not (0 <= product_index < len(self.products)):
            raise IndexError("Product index out of range.")

        # row_group is an N-element tuple containing the bundled rows
        return [
            getattr(row_group[product_index], id_col) for row_group in self.raw_results
        ]

    def to_dicts(self, prefixes: str | None = None):
        """
        Flattens the N-tuple records into single dictionaries.
        Auto-generates key name prefixes from product names by default, optionally provide prefixes.
        """
        if prefixes is None:
            prefixes = [str(product.name) for product in self.products]

        if len(prefixes) != len(self.products):
            raise ValueError(
                f"Expected {len(self.products)} prefixes, got {len(prefixes)}"
            )

        # produce a list of dicts (products) of dicts(fields)
        flattened = []
        for row_group in self.raw_results:
            merged_dict = {}
            for idx, row in enumerate(row_group):
                prefix = prefixes[idx]
                merged_dict.update({prefix: dict(row._mapping)})
            flattened.append(merged_dict)

        return flattened

    def create_combined_table(self, db, table_name: str, prefixes=None):
        """
        Dynamically generates a new database table combining columns from all products.
        """
        if prefixes is None:
            prefixes = [f"t{i}_" for i in range(len(self.products))]

        new_columns = []

        # Clone column definitions from all Products dynamically
        for idx, product in enumerate(self.products):
            table = product.get_table(db)
            prefix = prefixes[idx]

            for col in table.c:
                new_columns.append(Column(f"{prefix}{col.name}", type_=col.type))

        # Define and create the new table
        combined_table = Table(
            table_name, db.metadata, *new_columns, extend_existing=True
        )
        combined_table.create(db.engine, checkfirst=True)

        # Bulk insert the flattened records
        records = self.to_dicts(prefixes)
        if records:
            with db.engine.begin() as conn:
                conn.execute(combined_table.insert(), records)

        return combined_table

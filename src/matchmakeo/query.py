from geoalchemy2.functions import ST_MakeEnvelope
from sqlalchemy import and_, func
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from .databases import Database
from .product import Product


class Query:
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

        # Safely extract the underlying SQLAlchemy Table object from each Product
        self.tables = [p.get_table(self._database) for p in products]

        # Initialize the query with all target tables
        self._query = self._session.query(*self.tables)

        # PERFORMANCE SAFEGUARD: Only chain the baseline spatial index join
        # if the user is matching two or more tables together.
        if len(self.tables) > 1:
            for i in range(len(self.tables) - 1):
                geom_a = self.tables[i].c.geometry
                geom_b = self.tables[i + 1].c.geometry
                self._query = self._query.filter(geom_a.ST_Intersects(geom_b))

    def _get_table_obj(self, product):
        """Helper to safely fetch and validate a product's underlying table."""
        if product is None:
            if len(self.products) == 1:
                return self.tables[0]
            raise ValueError(
                "You must specify which Product to filter when matching multiple products."
            )

        if product not in self.products:
            raise ValueError(
                f"Product '{product}' was not provided during initialization."
            )
        return product.get_table(self._database)

    # ==========================================
    # SINGLE & MULTI-PRODUCT FILTERS
    # ==========================================

    def in_time_range(
        self, start_date, end_date, product: Product, attr_name: str = "timestamp"
    ):
        """Filters a single product's records within a absolute time range."""
        table = self._get_table_obj(product)
        time_col = getattr(table.c, attr_name)
        self._query = self._query.filter(time_col.between(start_date, end_date))
        return self

    def within_bbox(
        self, min_x, min_y, max_x, max_y, product: Product, srid: int = 4326
    ):
        """Filters a single product's records within a bounding box spatial envelope."""
        table = self._get_table_obj(product)
        bbox = func.ST_MakeEnvelope(min_x, min_y, max_x, max_y, srid)
        self._query = self._query.filter(table.c.geometry.ST_Intersects(bbox))
        return self

    def within_polygon(self):
        raise NotImplementedError

    def intersects_path(self):
        raise NotImplementedError

    # ==========================================
    # PAIRWISE CROSS-TABLE JOIN FILTERS
    # ==========================================

    def where_spatial_overlap(
        self, product_x, product_y, min_percentage: float, relative_to: str = "first"
    ):
        """Filters pairs of records based on how much their polygons overlap."""
        table_x = self._get_table_obj(product_x)
        table_y = self._get_table_obj(product_y)

        intersection_area = func.ST_Area(
            func.ST_Intersection(table_x.c.geom, table_y.c.geom)
        )

        if relative_to == "first":
            base_area = func.ST_Area(table_x.c.geom)
        elif relative_to == "second":
            base_area = func.ST_Area(table_y.c.geom)
        elif relative_to == "union":
            base_area = func.ST_Area(func.ST_Union(table_x.c.geom, table_y.c.geom))
        else:
            raise ValueError("relative_to must be 'first', 'second', or 'union'")

        percentage_calculation = (intersection_area / func.nullif(base_area, 0)) * 100
        self._query = self._query.filter(percentage_calculation >= min_percentage)
        return self

    def where_time_overlaps(
        self,
        product_x,
        product_y,
        start_attr: str = "timestamp",
        end_attr: str | None = None,
    ):
        """Filters pairs of records where their timestamps or time windows intersect."""
        table_x = self._get_table_obj(product_x)
        table_y = self._get_table_obj(product_y)

        x_start = getattr(table_x.c, start_attr)
        y_start = getattr(table_y.c, start_attr)

        if end_attr:
            x_end = getattr(table_x.c, end_attr)
            y_end = getattr(table_y.c, end_attr)
            self._query = self._query.filter(and_(x_start <= y_end, x_end >= y_start))
        else:
            self._query = self._query.filter(x_start == y_start)

        return self

    def where_property_match(self, product_x, attr_x: str, product_y, attr_y: str):
        """Filters pairs where metadata properties match across tables."""
        table_x = self._get_table_obj(product_x)
        table_y = self._get_table_obj(product_y)

        self._query = self._query.filter(
            getattr(table_x.c, attr_x) == getattr(table_y.c, attr_y)
        )
        return self

    def execute(self):
        """Executes the query and yields the resulting data rows."""
        try:
            return self._query.all()
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

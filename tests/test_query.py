import datetime
import json
import os

import pytest
import shapely
from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Integer, MetaData, Table

from matchmakeo import MatchResultSet, Product, Query, ResultSet


def _build_mock_product(db, fixtures_file, table_name, date_fields):
    """
    Generic helper to construct a dynamic table, insert JSON mock data,
    and return the metadata and Product instance for testing.
    """
    metadata = MetaData()

    columns = [
        Column("id", Integer, primary_key=True),
        Column("timestamp", DateTime, nullable=False),
        Column("geometry", Geometry("POLYGON", srid=4326), nullable=False),
    ]
    table = Table(table_name, metadata, *columns)
    db.create_engine()
    metadata.create_all(db.engine)

    records_to_insert = []
    with open(fixtures_file, "r") as f:
        fixture = json.load(f)
    for row in fixture:
        record = row.copy()

        for field in date_fields:
            if field in record:
                record[field] = datetime.datetime.fromisoformat(record[field])
        records_to_insert.append(record)

    with db.connect() as conn:
        conn.execute(table.insert(), records_to_insert)
        conn.commit()

    return metadata, Product(table_name)


@pytest.fixture(scope="function")
def product_a(database, filepath=None):
    """Creates product table and populates it from JSON."""

    if filepath is None:
        filepath = os.path.join("tests", "fixtures", "dummy_product_a.json")

    metadata, product = _build_mock_product(
        db=database,
        fixtures_file=filepath,
        table_name="product_a",
        date_fields=["timestamp"],
    )

    yield product
    metadata.drop_all(database.engine)


@pytest.fixture(scope="function")
def product_b(database, filepath=None):
    """Creates product table and populates it from JSON."""

    if filepath is None:
        filepath = os.path.join("tests", "fixtures", "dummy_product_b.json")

    metadata, product = _build_mock_product(
        db=database,
        fixtures_file=filepath,
        table_name="product_b",
        date_fields=["timestamp"],
    )

    yield product
    metadata.drop_all(database.engine)


class TestSingleProductQuery:
    def test_query_in_time_range(self, database, product_a, product_b):

        # initialisation with no products should raise an error
        with pytest.raises(ValueError):
            Query(database)

        # construct a query object
        Query(database, product_a, product_b)

        # perform simple query
        results = (
            Query(database, product_a)
            .in_time_range(
                start_time=datetime.datetime.fromisoformat("2026-07-14T11:00:00"),
                end_time=datetime.datetime.fromisoformat("2026-07-14T12:00:00"),
                product=product_a,
            )
            .execute()
        )
        assert isinstance(results, ResultSet)
        assert len(results) == 5
        assert results.get_ids() == [1, 2, 3, 4, 5]

    def test_query_param_equals(self, database, product_a):
        results = (
            Query(database, product_a).with_param_equal(params={"id": 1}).execute()
        )
        assert isinstance(results, ResultSet)
        assert len(results) == 1
        assert results.get_ids() == [1]

    def test_query_param_lt(self, database, product_a):
        results = Query(database, product_a).with_param_lt(params={"id": 3}).execute()
        assert isinstance(results, ResultSet)
        assert len(results) == 2
        assert results.get_ids() == [1, 2]

    def test_query_param_le(self, database, product_a):
        results = (
            Query(database, product_a)
            .with_param_le(
                params={
                    "id": 3,
                }
            )
            .execute()
        )
        assert isinstance(results, ResultSet)
        assert len(results) == 3
        assert results.get_ids() == [1, 2, 3]

    def test_query_param_ge(self, database, product_a):
        results = Query(database, product_a).with_param_ge(params={"id": 3}).execute()
        assert isinstance(results, ResultSet)
        assert len(results) == 3
        assert results.get_ids() == [3, 4, 5]

    def test_query_param_gt(self, database, product_a):
        results = Query(database, product_a).with_param_gt(params={"id": 3}).execute()
        assert isinstance(results, ResultSet)
        assert len(results) == 2
        assert results.get_ids() == [4, 5]

    def test_query_intersects_bbox(self, database, product_a):

        results = (
            Query(database, product_a)
            .intersects_bbox(
                xmin=0.077591,
                ymin=52.169931,
                xmax=0.190887,
                ymax=52.233477,
                product=product_a,
                srid=4326,
            )
            .execute()
        )
        assert isinstance(results, ResultSet)
        assert len(results) == 1

        # tests for ResultSet
        results_list = results.to_dicts()
        assert results.get_ids() == [1]
        assert isinstance(results_list, list)
        for element in results_list:
            assert isinstance(element, dict)

    def test_query_intersects_polygon(self, database, product_a):

        polygon = shapely.box(
            xmin=0.077591,
            ymin=52.169931,
            xmax=0.190887,
            ymax=52.233477,
        )

        results = (
            Query(database, product_a)
            .intersects_polygon(
                polygon=polygon,
            )
            .execute()
        )
        assert isinstance(results, ResultSet)
        assert len(results) == 1


class TestMultiProductQuery:
    def test_intersect_query(self, database, product_a, product_b):
        results = (
            Query(database, product_a, product_b)
            .where_spatial_overlap(
                min_overlap_fraction=0.1,
                relative_to=product_a,
            )
            .execute()
        )

        # plot for debugging
        # from .utils import visualise_matched_pairs
        # import matplotlib
        # matplotlib.use("Agg")
        # visualise_matched_pairs(
        #             results,
        #             id_attrs=("id", "id"),
        #             time_attrs=("timestamp", "timestamp")
        #         )

        assert isinstance(results, MatchResultSet)
        assert len(results) == 2

        # tests for MatchResultSet
        results_list = results.to_dicts()
        assert isinstance(results_list, list)
        for element in results_list:
            assert isinstance(element, dict)
            for values in element.values():
                assert isinstance(values, dict)

    def test_time_within_query(self, database, product_a, product_b):
        results = (
            Query(database, product_a, product_b)
            .where_time_within(
                max_time_delta=datetime.timedelta(days=2),
                product_x=product_a,
                product_y=product_b,
            )
            .execute()
        )
        assert isinstance(results, MatchResultSet)
        assert len(results) == 3

    def test_spatiotemporal_intersect_query(self, database, product_a, product_b):
        results = (
            Query(database, product_a, product_b)
            .where_spatiotemporal_match(
                relative_to=product_a,
                min_overlap_fraction=0.1,
                max_time_delta=datetime.timedelta(days=2),
            )
            .execute()
        )

        # plot for debugging
        # from .utils import visualise_matched_pairs
        # import matplotlib
        # matplotlib.use("Agg")
        # visualise_matched_pairs(
        #     results,
        #     id_attrs=("id", "id"),
        #     time_attrs=("timestamp", "timestamp")
        # )
        assert isinstance(results, MatchResultSet)
        assert len(results) == 2


class TestChainedQuery:
    def test_chained_spatiotemporal_intersect_query(
        self, database, product_a, product_b
    ):
        single_query_results = (
            Query(database, product_a, product_b)
            .where_spatiotemporal_match(
                relative_to=product_a,
                min_overlap_fraction=0.1,
                max_time_delta=datetime.timedelta(days=2),
            )
            .execute()
        )

        chained_query_results = (
            Query(database, product_a, product_b)
            .where_time_within(
                max_time_delta=datetime.timedelta(days=2),
                product_x=product_a,
                product_y=product_b,
            )
            .where_spatial_overlap(
                min_overlap_fraction=0.1,
                relative_to=product_a,
            )
            .execute()
        )

        assert len(single_query_results) == len(chained_query_results)
        assert single_query_results.to_dicts() == chained_query_results.to_dicts()

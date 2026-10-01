import datetime

import pytest
import shapely
import sqlalchemy
from sqlalchemy.orm import Session

from matchmakeo import MatchResultSet, Query, ResultSet


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

        with pytest.raises(ValueError):
            # pass a polygon with no srid and polygon with no srid
            # should raise a value error
            results = (
                Query(database, product_a)
                .intersects_polygon(
                    polygon=polygon,
                )
                .execute()
            )

        results = (
            Query(database, product_a)
            .intersects_polygon(
                polygon=polygon,
                srid=4326,
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


class TestCreateResultTable:
    def test_create_result_table(self, database, product_a, product_b):
        results = (
            Query(database, product_a, product_b)
            .where_spatiotemporal_match(
                relative_to=product_a,
                min_overlap_fraction=0.1,
                max_time_delta=datetime.timedelta(days=2),
            )
            .execute()
        )

        expected_num_results = 2

        assert isinstance(results, MatchResultSet)
        assert len(results) == expected_num_results

        table_name = "ab_overlap"
        results.create_combined_table(database, table_name=table_name)

        metadata = sqlalchemy.MetaData()
        table = sqlalchemy.Table(table_name, metadata, autoload_with=database.engine)

        with Session(database.engine) as session:
            statement = sqlalchemy.select(table)
            rows = session.execute(statement).all()
            assert len(rows) == expected_num_results

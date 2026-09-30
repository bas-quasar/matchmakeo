import logging

import pytest
import sqlalchemy

from matchmakeo.product import Product


def test_product(caplog):

    p = Product(name="MOD021KM", table_name="MOD021KM")
    assert p.version is None
    del p

    with caplog.at_level(logging.WARNING):
        Product(name="MOD021KM")

    with pytest.raises(TypeError):
        Product(table_name="MOD021KM")


def test_product_table(database):
    prod_name = "test_prod_name"
    product = Product(name=prod_name, table_name=prod_name)

    # test for error on no table
    with pytest.raises(ValueError):
        product.get_table(database)

    # create the table
    metadata = database.metadata
    sqlalchemy.Table(
        prod_name,
        metadata,
        sqlalchemy.Column("pk", sqlalchemy.Integer, primary_key=True),
    ).create(database.connect(), checkfirst=True)
    database.connection.commit()

    # test table is correct
    table = product.get_table(database)
    assert isinstance(table, sqlalchemy.Table)
    assert table.name == product.table_name


def test_product_geometry_column():
    prod_name = "test_prod_name"

    # using default behaviour
    product = Product(name=prod_name, table_name=prod_name)
    assert product.geometry_column == "geometry"

    # setting custom value after initialisation
    product.geometry_column = "granule"
    assert product.geometry_column == "granule"

    prod_name = "test_prod_name_2"
    product_2 = Product(
        name=prod_name, table_name=prod_name, geometry_column="footprint"
    )
    assert product_2.geometry_column == "footprint"

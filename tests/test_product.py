import pytest
import sqlalchemy

from matchmakeo.product import Product

def test_product():

    p = Product(name="MOD021KM", table_name="MOD021KM")
    assert p.version is None
    del p

    # mainly because I don't trust dataclasses
    with pytest.raises(TypeError):
        p = Product(name="MOD021KM")

    with pytest.raises(TypeError):
        p = Product(table_name="MOD021KM")

def test_product_table(database):
    prod_name = "test_prod_name"
    product = Product(name=prod_name, table_name=prod_name)
    
    # test for error on no table
    with pytest.raises(ValueError):
        product.get_table(database)

    # create the table
    metadata = sqlalchemy.MetaData()
    sqlalchemy.Table(
        prod_name,
        metadata,
        sqlalchemy.Column("pk", sqlalchemy.Integer, primary_key=True)
        ).create(database.connect(), checkfirst=True)
    database.connection.commit()

    # test table is correct
    table = product.get_table(database)
    assert isinstance(table, sqlalchemy.Table)
    assert table.name == product.table_name
    

import pytest

from matchmakeo.product import Product

def test_product():

    p = Product(name="MOD021KM", table="MOD021KM")
    assert p.version is None
    del p

    # mainly because I don't trust dataclasses
    with pytest.raises(TypeError):
        p = Product(name="MOD021KM")

    with pytest.raises(TypeError):
        p = Product(table="MOD021KM")

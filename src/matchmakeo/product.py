from dataclasses import dataclass, field

import sqlalchemy
from sqlalchemy.exc import NoSuchTableError

from .databases import Database
from .utils import setUpLogging

__all__ = [
    "Product"
]

log = setUpLogging(__name__)

@dataclass
class Product:
    """Class representing a data product.
    """

    name: str
    table_name: str
    extra_fields: list = field(default_factory=list)
    version: int = None

    def get_table(self, database: Database):
        "The table object corresponding to the product."

        inspector = sqlalchemy.inspect(database.create_engine())
        
        # Check if the table exists in the database first
        if not inspector.has_table(self.table_name):
            raise ValueError(f"Table '{self.table_name}' does not exist in the database.")
        
        metadata = sqlalchemy.MetaData()
        return sqlalchemy.Table(self.table_name, metadata, autoload_with=database.engine)

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
    """
    Class representing a data product.

    Args:
        name (str): name used for downloading the product.
        table_name (str): Name for the corresponding database table. Default: None. If not given, name will be used.
        extra_fields (list):
        version (int): version used for downloading the product if required.
    """

    name: str
    table_name: str = None
    extra_fields: list = field(default_factory=list)
    version: int = None

    def __post_init__(self):
        if not self.table_name:
            log.warning(f"No table_name specified, setting table_name to name {self.name}")
            self.table_name = self.name

    def get_table(self, database: Database):
        "The table object corresponding to the product."

        inspector = sqlalchemy.inspect(database.create_engine())
        
        # Check if the table exists in the database first
        if not inspector.has_table(self.table_name):
            raise ValueError(f"Table '{self.table_name}' does not exist in the database.")
        
        metadata = sqlalchemy.MetaData()
        return sqlalchemy.Table(self.table_name, metadata, autoload_with=database.engine)

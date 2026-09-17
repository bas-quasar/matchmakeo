import sqlalchemy

from .databases import Database
from .utils import setUpLogging

__all__ = ["Product"]


log = setUpLogging(__name__)


class Product:
    """
    Class representing a data product.

    Args:
        name (str): name used for downloading the product.
        table_name (str): Name for the corresponding database table. Default: None. If not given, name will be used.
        extra_fields (list):
        version (int): version used for downloading the product if required.
    """

    def __init__(
        self,
        name: str,
        table_name: str | None = None,
        extra_fields: list | None = None,
        version: int | None = None,
    ):
        if extra_fields is None:
            extra_fields = []
        self.name = name
        self.table_name = table_name
        self.extra_fields = extra_fields
        self.version = version
        self._table = None

        if not table_name:
            log.warning(
                f"No table_name specified, setting table_name to name {self.name}"
            )
            self.table_name = self.name

    def get_table(self, database: Database):
        "The table object corresponding to the product."

        metadata = database.metadata
        if self._table is None:
            inspector = sqlalchemy.inspect(database.create_engine())

            # Check if the table exists in the database first
            if not inspector.has_table(self.table_name):
                raise ValueError(
                    f"Table '{self.table_name}' does not exist in the database."
                )

            self._table = sqlalchemy.Table(
                self.table_name, metadata, autoload_with=database.engine
            )
        return self._table

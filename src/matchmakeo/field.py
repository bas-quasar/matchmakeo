from sqlalchemy import Column
from sqlalchemy.sql.type_api import TypeEngine


class Field(dict):
    """Fields to be created in database."""

    def __init__(self, catalogue_name: str, column_name: str, column_type: TypeEngine):
        self.catalogue_name = catalogue_name
        self.column_name = column_name

        if isinstance(column_type, TypeEngine) or issubclass(column_type, TypeEngine):
            self.type = column_type
        else:
            warnings.warn(
                f"Custom field types must be SQL Alchemy types. Got {type(column_type)} for {column_name}.\n\
                          Unexpected behaviour may occur."
            )

    def _as_column(self):
        return Column(self.column_name, self.type)

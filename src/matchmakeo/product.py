from dataclasses import dataclass, field

__all__ = ["Product"]


@dataclass
class Product:
    """Class representing a data product."""

    name: str
    table: str
    extra_fields: list = field(default_factory=list)
    version: int = None

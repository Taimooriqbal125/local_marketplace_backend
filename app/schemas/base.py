import re
from typing import Any

from pydantic import BaseModel, ConfigDict


def to_camel(string: str) -> str:
    """
    Convert a snake_case string to camelCase.
    Example: is_admin -> isAdmin
    """
    return re.sub(r"_([a-z])", lambda x: x.group(1).upper(), string)


class BaseSchema(BaseModel):
    """
    Standard base schema for all Pydantic models in the application.
    
    Features:
    - Automatic camelCase aliases for all fields.
    - Support for SQLAlchemy model attribute mapping (from_attributes=True).
    - Allows populating models by both field name and alias (populate_by_name=True).
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

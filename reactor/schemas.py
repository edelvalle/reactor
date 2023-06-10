from enum import StrEnum

from pydantic import BaseModel, Field


class AutoBroadcast(BaseModel):
    model: bool = False
    model_pk: bool = False
    related: bool = False
    m2m: bool = False
    senders: set[tuple[str, str]] = Field(default_factory=set)


class ModelAction(StrEnum):
    # Model action
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    CREATED = "CREATED"

    # M2M actions
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    CLEARED = "CLEARED"


class DomAction(StrEnum):
    APPEND = "append"
    PREPEND = "prepend"
    INSERT_AFTER = "insert_after"
    INSERT_BEFORE = "insert_before"
    REPLACE_WITH = "replace_with"

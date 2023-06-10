from enum import StrEnum

from pydantic import BaseModel, Field


class AutoBroadcast(BaseModel):
    # model-a
    model: bool = False
    # model-a.1234
    model_pk: bool = False
    # model-b.9876.model-a-set
    related: bool = False
    # model-b.9876.model-a-set
    # model-a.1234.model-b-set
    m2m: bool = False
    # this is a set of tuples of ('app_label', 'ModelName')
    # to subscribe for the auto broadcast
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

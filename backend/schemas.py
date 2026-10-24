from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SuggestedItem(BaseModel):
    source_id: int
    quote: str = Field(min_length=5, max_length=2000)
    title: str = Field(min_length=3, max_length=160)
    kind: Literal['transport', 'errand', 'appointment', 'pickup', 'confirmation']
    due_at: datetime | None = Field(description='ISO date/time using source_timezone_offset for local clock times. Null if the date or time is unknown.')
    owner: str | None
    location: str | None
    uncertainty: str | None
    change: Literal['new', 'reschedule', 'cancel'] = 'new'
    related_task_id: int | None = None


class Extraction(BaseModel):
    items: list[SuggestedItem] = Field(max_length=50)


class ImportRequest(BaseModel):
    text: str = Field(min_length=5, max_length=24000)
    reference_at: datetime
    label: str = Field(default='Pasted messages', min_length=1, max_length=100)
    synthetic: bool = True
    visibility: Literal['circle', 'private'] = 'circle'

    @field_validator('reference_at')
    @classmethod
    def timezone_required(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Include a timezone offset in the reference timestamp.')
        return value


class ReviewRequest(BaseModel):
    decision: Literal['approve', 'reject']
    title: str = Field(min_length=3, max_length=160)
    kind: Literal['transport', 'errand', 'appointment', 'pickup', 'confirmation'] | None = None
    due_at: datetime | None = None
    owner_id: int | None = Field(default=None, ge=1)
    location: str = Field(default='', max_length=200)
    uncertainty: str = Field(default='', max_length=500)
    acknowledge_uncertainty: bool = False
    related_task_id: int | None = Field(default=None, ge=1)
    version: int

    @field_validator('due_at')
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError('Include a timezone offset in the due timestamp.')
        return value


class AvailabilityRequest(BaseModel):
    start_at: datetime
    end_at: datetime
    note: str = Field(default='Unavailable', max_length=160)


class PermissionRequest(BaseModel):
    can_import: bool
    can_review: bool
    can_brief: bool


class DraftRequest(BaseModel):
    day: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')


class DraftSelection(BaseModel):
    task_ids: list[int] = Field(max_length=50)

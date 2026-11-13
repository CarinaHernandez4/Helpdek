"""Esquemas del modulo "Registro de tiempo de atencion" (work logs).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkLogCreate(BaseModel):
    minutes: int = Field(ge=1, le=1440)
    note: str = Field(min_length=1)


class WorkLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author_id: int
    minutes: int
    note: str
    created_at: datetime


class WorkLogListOut(BaseModel):
    items: list[WorkLogOut]
    total_minutes: int

"""Schemas for device API (2 endpoints)."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SensorCountCreate(BaseModel):
    """POST /api/v1/sensor/count"""
    device_id: str = Field(pattern=r"^[a-z0-9_]{5,50}$")
    timestamp: datetime
    up_count: int = Field(ge=0)
    down_count: int = Field(ge=0)
    battery_pct: Optional[int] = Field(default=None, ge=0, le=100)
    temperature_c: Optional[float] = None


class SensorCountResponse(BaseModel):
    id: str
    device_id: str
    location_id: str
    timestamp: datetime
    status: str = "accepted"


class CameraUploadResponse(BaseModel):
    id: str
    camera_id: str
    storage_path: str
    analysis_status: str = "pending"

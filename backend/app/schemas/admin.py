"""Schemas for admin API (15 endpoints)."""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


# --- Pagination ---
class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    sort: str = "created_at"
    order: str = "desc"


class PaginatedResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list


# --- /admin/dashboard ---
class DashboardSummary(BaseModel):
    total_ascending: int
    total_descending: int
    on_mountain: int
    device_uptime_pct: float

class AlertSummary(BaseModel):
    id: str
    alert_type: str
    title: str
    message: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    is_read: bool
    created_at: datetime

class DashboardResponse(BaseModel):
    summary: DashboardSummary
    alerts: list[AlertSummary]
    hourly: list[dict]
    route_breakdown: list[dict]


# --- /admin/devices ---
class DeviceItem(BaseModel):
    id: str
    device_id: str
    location_name: str
    device_type: str
    status: str
    battery_pct: Optional[int] = None
    temperature_c: Optional[float] = None
    last_data_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    maintenance_notes: Optional[str] = None

class DeviceListResponse(BaseModel):
    devices: list[DeviceItem]

class DeviceUpdateRequest(BaseModel):
    status: Optional[str] = None
    maintenance_notes: Optional[str] = None


# --- /admin/calibration ---
class CalibrationFactorItem(BaseModel):
    id: str
    location_name: str
    weather: str
    ascending_factor: float
    descending_factor: float
    sample_days: int
    confidence_pct: Optional[int] = None
    valid_from: date
    valid_to: date

class CalibrationFactorUpdate(BaseModel):
    ascending_factor: Optional[float] = None
    descending_factor: Optional[float] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

class CalibrationRecordItem(BaseModel):
    id: str
    location_name: str
    date: date
    time_slot: str
    weather: str
    manual_ascending: int
    manual_descending: int
    ir_ascending: Optional[int] = None
    ir_descending: Optional[int] = None
    correction_factor: Optional[float] = None
    operator: Optional[str] = None

class CalibrationRecordCreate(BaseModel):
    location_id: str
    date: date
    time_slot: str = Field(pattern=r"^\d{2}-\d{2}$")
    weather: str = Field(pattern=r"^(clear|cloudy|rain)$")
    manual_ascending: int = Field(ge=0)
    manual_descending: int = Field(ge=0)
    operator: Optional[str] = None


# --- /admin/camera-analysis ---
class CameraAnalysisItem(BaseModel):
    id: str
    camera_id: str
    capture_timestamp: datetime
    detected_person_count: int
    group_count: Optional[int] = None
    ir_count_at_time: Optional[int] = None
    confidence_score: Optional[float] = None
    correction_suggestion: Optional[str] = None

class CameraAnalysisResponse(BaseModel):
    total: int
    items: list[CameraAnalysisItem]


# --- /admin/site-analysis ---
class SiteAnalysisItem(BaseModel):
    location_name: str
    prefecture: str
    device_type: str
    device_count: int
    active_count: int
    last_data_at: Optional[datetime] = None
    uptime_pct: Optional[float] = None

class SiteAnalysisResponse(BaseModel):
    total_locations: int
    active_devices: int
    total_devices: int
    avg_uptime_pct: float
    sites: list[SiteAnalysisItem]


# --- /admin/history ---
class HistoryParams(BaseModel):
    year: Optional[int] = None
    location_id: Optional[str] = None
    granularity: str = "month"  # day / week / month


# --- /admin/trail-status ---
class TrailStatusCreate(BaseModel):
    route_id: Optional[str] = None
    status_type: str = Field(pattern=r"^(caution|info|danger)$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    source: Optional[str] = None

class TrailStatusUpdate(BaseModel):
    status_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    is_active: Optional[bool] = None


# --- /admin/alerts ---
class AlertCreate(BaseModel):
    alert_type: str
    location_id: Optional[str] = None
    title: str
    message: Optional[str] = None

class AlertUpdate(BaseModel):
    is_read: Optional[bool] = None
    message: Optional[str] = None

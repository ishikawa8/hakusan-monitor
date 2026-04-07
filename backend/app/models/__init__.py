"""SQLAlchemy ORM models for all 16 tables."""

from app.models.tables import (
    Location,
    Route,
    Waypoint,
    Facility,
    Device,
    SensorCount,
    HourlyCount,
    RouteRealtime,
    CalibrationRecord,
    CalibrationFactor,
    CameraImage,
    CameraAnalysis,
    TrailStatus,
    Lodging,
    Alert,
    DeviceStatusLog,
)

__all__ = [
    "Location",
    "Route",
    "Waypoint",
    "Facility",
    "Device",
    "SensorCount",
    "HourlyCount",
    "RouteRealtime",
    "CalibrationRecord",
    "CalibrationFactor",
    "CameraImage",
    "CameraAnalysis",
    "TrailStatus",
    "Lodging",
    "Alert",
    "DeviceStatusLog",
]

"""All 16 database table definitions per design doc v2.2."""

import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Text, Integer, SmallInteger, Boolean, Date,
    DateTime, Numeric, ForeignKey, Index, UniqueConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


def new_uuid():
    return uuid.uuid4()


# ---------- 3.2.1 locations ----------
class Location(Base):
    __tablename__ = "locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name = Column(Text, nullable=False)
    prefecture = Column(Text, nullable=False)
    latitude = Column(Numeric)
    longitude = Column(Numeric)
    elevation = Column(Integer)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # relationships
    devices = relationship("Device", back_populates="location")
    sensor_counts = relationship("SensorCount", back_populates="location")
    hourly_counts = relationship("HourlyCount", back_populates="location")
    calibration_records = relationship("CalibrationRecord", back_populates="location")
    calibration_factors = relationship("CalibrationFactor", back_populates="location")
    alerts = relationship("Alert", back_populates="location")


# ---------- 3.2.2 routes ----------
class Route(Base):
    __tablename__ = "routes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name = Column(Text, nullable=False)
    description = Column(Text)
    description_long = Column(Text)
    start_location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    usage_percentage = Column(Numeric)
    elevation_gain = Column(Integer)
    difficulty = Column(Text)
    duration_hours = Column(Numeric)
    is_recommended = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)

    # relationships
    start_location = relationship("Location")
    waypoints = relationship("Waypoint", back_populates="route", order_by="Waypoint.sort_order")
    facilities = relationship("Facility", back_populates="route")
    realtime = relationship("RouteRealtime", back_populates="route")
    lodgings = relationship("Lodging", back_populates="route")
    trail_statuses = relationship("TrailStatus", back_populates="route")


# ---------- 3.2.3 waypoints ----------
class Waypoint(Base):
    __tablename__ = "waypoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False)
    name = Column(Text, nullable=False)
    elevation = Column(Integer, nullable=False)
    course_time_min = Column(Integer)
    has_toilet = Column(Boolean, nullable=False, default=False)
    has_water = Column(Boolean, nullable=False, default=False)
    has_shelter = Column(Boolean, nullable=False, default=False)
    description = Column(Text)
    retreat_warning = Column(Text)
    is_confusing_point = Column(Boolean, nullable=False, default=False)
    warning_text = Column(Text)
    sort_order = Column(Integer, nullable=False, default=0)

    route = relationship("Route", back_populates="waypoints")


# ---------- 3.2.4 facilities ----------
class Facility(Base):
    __tablename__ = "facilities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name = Column(Text, nullable=False)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    elevation = Column(Integer)
    has_toilet = Column(Boolean, nullable=False, default=False)
    has_water = Column(Boolean, nullable=False, default=False)
    has_shelter = Column(Boolean, nullable=False, default=False)
    has_hot_spring = Column(Boolean, nullable=False, default=False)
    lodging_type = Column(Text)  # '要予約' / '予約不要' / NULL
    notes = Column(Text)

    route = relationship("Route", back_populates="facilities")


# ---------- 3.2.5 devices ----------
class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    device_id = Column(Text, nullable=False, unique=True, index=True)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    device_type = Column(Text, nullable=False)  # 'ir_sensor' / 'camera_a' / 'camera_b'
    model = Column(Text)
    status = Column(Text, nullable=False, default="active")
    battery_pct = Column(SmallInteger)
    temperature_c = Column(Numeric)
    last_data_at = Column(DateTime(timezone=True))
    last_heartbeat = Column(DateTime(timezone=True))
    installed_at = Column(DateTime(timezone=True))
    maintenance_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    location = relationship("Location", back_populates="devices")
    status_logs = relationship("DeviceStatusLog", back_populates="device",
                               foreign_keys="DeviceStatusLog.device_id_fk")


# ---------- 3.2.6 sensor_counts ----------
class SensorCount(Base):
    __tablename__ = "sensor_counts"
    __table_args__ = (
        Index("idx_sensor_counts_loc_ts", "location_id", "timestamp"),
        Index("idx_sensor_counts_dev_ts", "device_id", "timestamp"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    device_id = Column(Text, nullable=False)  # FK → devices.device_id (logical)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    up_count = Column(Integer, nullable=False)
    down_count = Column(Integer, nullable=False)
    battery_pct = Column(SmallInteger)
    temperature_c = Column(Numeric)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    location = relationship("Location", back_populates="sensor_counts")


# ---------- 3.2.7 hourly_counts ----------
class HourlyCount(Base):
    __tablename__ = "hourly_counts"
    __table_args__ = (
        UniqueConstraint("date", "location_id", "hour", name="uq_hourly_counts"),
        Index("idx_hourly_counts_date_loc", "date", "location_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    date = Column(Date, nullable=False)
    hour = Column(SmallInteger, nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    ascending = Column(Integer, nullable=False, default=0)
    descending = Column(Integer, nullable=False, default=0)
    cumulative_ascending = Column(Integer, nullable=False, default=0)
    cumulative_descending = Column(Integer, nullable=False, default=0)

    location = relationship("Location", back_populates="hourly_counts")


# ---------- 3.2.8 route_realtime ----------
class RouteRealtime(Base):
    __tablename__ = "route_realtime"
    __table_args__ = (
        UniqueConstraint("route_id", "date", name="uq_route_realtime"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False)
    date = Column(Date, nullable=False)
    ascending_count = Column(Integer, nullable=False, default=0)
    descending_count = Column(Integer, nullable=False, default=0)
    congestion_level = Column(Text, nullable=False, default="low")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    route = relationship("Route", back_populates="realtime")


# ---------- 3.2.9 calibration_records ----------
class CalibrationRecord(Base):
    __tablename__ = "calibration_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    date = Column(Date, nullable=False)
    time_slot = Column(Text, nullable=False)
    weather = Column(Text, nullable=False)
    manual_ascending = Column(Integer, nullable=False)
    manual_descending = Column(Integer, nullable=False)
    ir_ascending = Column(Integer)
    ir_descending = Column(Integer)
    correction_factor = Column(Numeric)
    operator = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    location = relationship("Location", back_populates="calibration_records")


# ---------- 3.2.10 calibration_factors ----------
class CalibrationFactor(Base):
    __tablename__ = "calibration_factors"
    __table_args__ = (
        UniqueConstraint("location_id", "weather", "valid_from", name="uq_cal_factors"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    weather = Column(Text, nullable=False)
    ascending_factor = Column(Numeric, nullable=False, default=1.0)
    descending_factor = Column(Numeric, nullable=False, default=1.0)
    sample_days = Column(Integer, nullable=False, default=0)
    confidence_pct = Column(SmallInteger)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=False)

    location = relationship("Location", back_populates="calibration_factors")


# ---------- 3.2.11 camera_images ----------
class CameraImage(Base):
    __tablename__ = "camera_images"
    __table_args__ = (
        Index("idx_camera_images_status", "analysis_status"),
        Index("idx_camera_images_cam_ts", "camera_id", "capture_timestamp"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    camera_id = Column(Text, nullable=False)  # FK → devices.device_id (logical)
    capture_timestamp = Column(DateTime(timezone=True), nullable=False)
    storage_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer)
    analysis_status = Column(Text, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    analysis = relationship("CameraAnalysis", back_populates="image", uselist=False)


# ---------- 3.2.12 camera_analyses ----------
class CameraAnalysis(Base):
    __tablename__ = "camera_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    image_id = Column(UUID(as_uuid=True), ForeignKey("camera_images.id"), nullable=False, unique=True)
    detected_person_count = Column(Integer, nullable=False, default=0)
    group_count = Column(Integer)
    group_composition = Column(JSONB)
    ir_count_at_time = Column(Integer)
    confidence_score = Column(Numeric)
    correction_suggestion = Column(Text)
    raw_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    image = relationship("CameraImage", back_populates="analysis")


# ---------- 3.2.13 trail_status ----------
class TrailStatus(Base):
    __tablename__ = "trail_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    status_type = Column(Text, nullable=False)  # 'caution' / 'info' / 'danger'
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    source = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    route = relationship("Route", back_populates="trail_statuses")


# ---------- 3.2.14 lodging ----------
class Lodging(Base):
    __tablename__ = "lodging"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name = Column(Text, nullable=False)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    capacity = Column(Integer, nullable=False)
    reservation_required = Column(Boolean, nullable=False)
    price_text = Column(Text)
    occupancy_pct = Column(SmallInteger)
    tip = Column(Text)

    route = relationship("Route", back_populates="lodgings")


# ---------- 3.2.15 alerts ----------
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    alert_type = Column(Text, nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"))
    device_id = Column(Text)
    title = Column(Text, nullable=False)
    message = Column(Text)
    value = Column(Numeric)
    threshold = Column(Numeric)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    location = relationship("Location", back_populates="alerts")


# ---------- 3.2.16 device_status_log ----------
class DeviceStatusLog(Base):
    __tablename__ = "device_status_log"
    __table_args__ = (
        Index("idx_dsl_device_created", "device_id_fk", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    device_id_fk = Column(Text, ForeignKey("devices.device_id"), nullable=False)
    previous_status = Column(Text)
    new_status = Column(Text, nullable=False)
    battery_pct = Column(SmallInteger)
    changed_by = Column(Text)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    device = relationship("Device", back_populates="status_logs",
                          foreign_keys=[device_id_fk])

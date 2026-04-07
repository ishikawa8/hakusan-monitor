"""Schemas for public API responses (8 endpoints)."""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


# --- /public/weather ---
class MountainTopWeather(BaseModel):
    temperature_c: float
    feels_like_c: float
    wind_speed_kmh: float
    precipitation_pct: int
    wmo_code: int
    wmo_description: str
    sunrise: str
    sunset: str

class TrailheadWeather(BaseModel):
    temperature_c: float

class WeatherResponse(BaseModel):
    mountain_top: MountainTopWeather
    trailhead: TrailheadWeather
    grade: str  # A / B / C
    clothing: str
    wind_note: str
    cached_at: datetime


# --- /public/current ---
class LocationCurrent(BaseModel):
    id: str
    name: str
    ascending: int
    descending: int
    on_mountain: int
    congestion_level: str
    updated_at: datetime

class CurrentResponse(BaseModel):
    timestamp: datetime
    locations: list[LocationCurrent]


# --- /public/current/routes ---
class RouteCurrent(BaseModel):
    route_id: str
    route_name: str
    ascending_count: int
    descending_count: int
    on_mountain: int
    congestion_level: str
    usage_percentage: Optional[float] = None

class RouteCurrentResponse(BaseModel):
    timestamp: datetime
    routes: list[RouteCurrent]


# --- /public/hourly/:date ---
class HourlyEntry(BaseModel):
    hour: int
    ascending: int
    descending: int
    cumulative_ascending: int
    cumulative_descending: int

class HourlyResponse(BaseModel):
    date: date
    location_id: Optional[str] = None
    hours: list[HourlyEntry]


# --- /public/forecast/calendar ---
class ForecastDay(BaseModel):
    date: date
    day_of_week: str
    predicted_count: int
    congestion_level: str  # low / mid / high
    weather_code: Optional[int] = None

class ForecastCalendarResponse(BaseModel):
    days: list[ForecastDay]


# --- /public/forecast/dow ---
class DowEntry(BaseModel):
    day_of_week: str
    average_count: int

class ForecastDowResponse(BaseModel):
    entries: list[DowEntry]


# --- /public/trail-status ---
class TrailStatusItem(BaseModel):
    id: str
    route_name: Optional[str] = None
    status_type: str
    title: str
    description: str
    source: Optional[str] = None
    updated_at: datetime

class TrailStatusResponse(BaseModel):
    statuses: list[TrailStatusItem]


# --- /public/lodging ---
class LodgingItem(BaseModel):
    id: str
    name: str
    capacity: int
    reservation_required: bool
    price_text: Optional[str] = None
    occupancy_pct: Optional[int] = None
    tip: Optional[str] = None

class LodgingResponse(BaseModel):
    lodgings: list[LodgingItem]

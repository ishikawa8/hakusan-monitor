"""Public API router - 8 endpoints (no auth required)."""

import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import TrailStatus, Lodging, Route
from app.services.weather import fetch_weather

logger = logging.getLogger(__name__)
from app.services.congestion import (
    get_current_by_location, get_current_by_route,
    get_hourly, get_forecast_calendar, get_forecast_dow,
)
from app.schemas.public import (
    WeatherResponse, CurrentResponse, RouteCurrentResponse,
    HourlyResponse, ForecastCalendarResponse, ForecastDowResponse,
    TrailStatusResponse, TrailStatusItem, LodgingResponse, LodgingItem,
)

router = APIRouter(prefix="/api/v1/public", tags=["public"])


# --- GET /public/weather ---
@router.get("/weather")
async def get_weather():
    """山岳気象情報（Open-Meteo経由、1時間キャッシュ）"""
    try:
        return await fetch_weather()
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        raise HTTPException(
            status_code=503,
            detail="気象データを取得できません。しばらく後に再試行してください。"
        )


# --- GET /public/current ---
@router.get("/current")
async def get_current(db: AsyncSession = Depends(get_db)):
    """全登山口の現在混雑状況"""
    from datetime import datetime, timezone, timedelta
    locations = await get_current_by_location(db)
    return {
        "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "locations": locations,
    }


# --- GET /public/current/routes ---
@router.get("/current/routes")
async def get_current_routes(db: AsyncSession = Depends(get_db)):
    """ルート別リアルタイム混雑状況（5ルート）"""
    from datetime import datetime, timezone, timedelta
    routes = await get_current_by_route(db)
    return {
        "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "routes": routes,
    }


# --- GET /public/hourly/:date ---
@router.get("/hourly/{target_date}")
async def get_hourly_data(
    target_date: date,
    location_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """時間帯別入下山者数（チャート用）"""
    hours = await get_hourly(db, target_date, location_id)
    return {"date": target_date.isoformat(), "location_id": location_id, "hours": hours}


# --- GET /public/forecast/calendar ---
@router.get("/forecast/calendar")
async def get_forecast_calendar_endpoint(db: AsyncSession = Depends(get_db)):
    """2週間の混雑予測カレンダー"""
    days = await get_forecast_calendar(db)
    return {"days": days}


# --- GET /public/forecast/dow ---
@router.get("/forecast/dow")
async def get_forecast_dow_endpoint(db: AsyncSession = Depends(get_db)):
    """曜日別平均入山者数（チャート用）"""
    entries = await get_forecast_dow(db)
    return {"entries": entries}


# --- GET /public/trail-status ---
@router.get("/trail-status")
async def get_trail_status(db: AsyncSession = Depends(get_db)):
    """登山道の最新状況一覧"""
    rows = (await db.execute(
        select(TrailStatus, Route.name.label("route_name"))
        .outerjoin(Route, TrailStatus.route_id == Route.id)
        .where(TrailStatus.is_active == True)
        .order_by(TrailStatus.updated_at.desc())
    )).all()

    statuses = []
    for ts, route_name in rows:
        statuses.append(TrailStatusItem(
            id=str(ts.id),
            route_name=route_name,
            status_type=ts.status_type,
            title=ts.title,
            description=ts.description,
            source=ts.source,
            updated_at=ts.updated_at,
        ))
    return TrailStatusResponse(statuses=statuses)


# --- GET /public/lodging ---
@router.get("/lodging")
async def get_lodging(db: AsyncSession = Depends(get_db)):
    """山小屋・テント場の混雑状況"""
    rows = (await db.execute(select(Lodging))).scalars().all()
    items = [
        LodgingItem(
            id=str(r.id),
            name=r.name,
            capacity=r.capacity,
            reservation_required=r.reservation_required,
            price_text=r.price_text,
            occupancy_pct=r.occupancy_pct,
            tip=r.tip,
        ) for r in rows
    ]
    return LodgingResponse(lodgings=items)

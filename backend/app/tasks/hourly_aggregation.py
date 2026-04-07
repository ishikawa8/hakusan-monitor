"""Hourly aggregation task: sensor_counts → hourly_counts + route_realtime."""

import logging
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models import SensorCount, HourlyCount, RouteRealtime, Device, Route
from app.services.congestion import congestion_level

logger = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))


async def aggregate_hourly(target_date: date = None):
    """Aggregate sensor_counts into hourly_counts for the given date."""
    if target_date is None:
        target_date = datetime.now(JST).date()

    async with async_session() as db:
        # Get all sensor data for the date, grouped by location and hour
        rows = (await db.execute(
            select(
                SensorCount.location_id,
                func.extract("hour", SensorCount.timestamp).label("hour"),
                func.sum(SensorCount.up_count).label("total_up"),
                func.sum(SensorCount.down_count).label("total_down"),
            )
            .where(func.date(SensorCount.timestamp) == target_date)
            .group_by(SensorCount.location_id, "hour")
            .order_by(SensorCount.location_id, "hour")
        )).all()

        # Build cumulative counts per location
        location_data: dict = {}
        for r in rows:
            loc_id = str(r.location_id)
            if loc_id not in location_data:
                location_data[loc_id] = []
            location_data[loc_id].append({
                "hour": int(r.hour),
                "ascending": int(r.total_up),
                "descending": int(r.total_down),
            })

        count = 0
        for loc_id, hours in location_data.items():
            cum_asc = 0
            cum_desc = 0
            for h in sorted(hours, key=lambda x: x["hour"]):
                cum_asc += h["ascending"]
                cum_desc += h["descending"]

                # Upsert hourly_count
                existing = (await db.execute(
                    select(HourlyCount).where(
                        HourlyCount.date == target_date,
                        HourlyCount.location_id == loc_id,
                        HourlyCount.hour == h["hour"],
                    )
                )).scalar_one_or_none()

                if existing:
                    existing.ascending = h["ascending"]
                    existing.descending = h["descending"]
                    existing.cumulative_ascending = cum_asc
                    existing.cumulative_descending = cum_desc
                else:
                    db.add(HourlyCount(
                        date=target_date, hour=h["hour"], location_id=loc_id,
                        ascending=h["ascending"], descending=h["descending"],
                        cumulative_ascending=cum_asc, cumulative_descending=cum_desc,
                    ))
                count += 1

        await db.commit()
        logger.info(f"Aggregated {count} hourly records for {target_date}")

        # Update route_realtime
        await _update_route_realtime(db, target_date)


async def _update_route_realtime(db: AsyncSession, target_date: date):
    """Update route_realtime from hourly_counts via route→location mapping."""
    routes = (await db.execute(select(Route))).scalars().all()

    for route in routes:
        # Sum hourly counts for the route's start location
        total = (await db.execute(
            select(
                func.coalesce(func.max(HourlyCount.cumulative_ascending), 0).label("asc"),
                func.coalesce(func.max(HourlyCount.cumulative_descending), 0).label("desc"),
            )
            .where(
                HourlyCount.date == target_date,
                HourlyCount.location_id == route.start_location_id,
            )
        )).one()

        asc_count = int(total.asc)
        desc_count = int(total.desc)

        existing = (await db.execute(
            select(RouteRealtime).where(
                RouteRealtime.route_id == route.id,
                RouteRealtime.date == target_date,
            )
        )).scalar_one_or_none()

        if existing:
            existing.ascending_count = asc_count
            existing.descending_count = desc_count
            existing.congestion_level = congestion_level(asc_count)
            existing.updated_at = datetime.now(JST)
        else:
            db.add(RouteRealtime(
                route_id=route.id, date=target_date,
                ascending_count=asc_count, descending_count=desc_count,
                congestion_level=congestion_level(asc_count),
            ))

    await db.commit()
    logger.info(f"Updated route_realtime for {target_date}")

"""Congestion calculation and forecast services."""

from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import HourlyCount, RouteRealtime, Route, Location

JST = timezone(timedelta(hours=9))
DOW_JA = ["月", "火", "水", "木", "金", "土", "日"]


def congestion_level(count: int) -> str:
    """Determine congestion level based on daily count."""
    if count >= 250:
        return "high"
    elif count >= 100:
        return "mid"
    return "low"


async def get_current_by_location(db: AsyncSession) -> list[dict]:
    """Get current congestion for all active locations."""
    today = date.today()
    locations = (await db.execute(
        select(Location).where(Location.is_active == True)
    )).scalars().all()

    result = []
    for loc in locations:
        hourly = (await db.execute(
            select(HourlyCount)
            .where(HourlyCount.location_id == loc.id, HourlyCount.date == today)
            .order_by(HourlyCount.hour.desc())
        )).scalars().first()

        asc = hourly.cumulative_ascending if hourly else 0
        desc = hourly.cumulative_descending if hourly else 0
        on_mtn = max(asc - desc, 0)

        result.append({
            "id": str(loc.id),
            "name": loc.name,
            "ascending": asc,
            "descending": desc,
            "on_mountain": on_mtn,
            "congestion_level": congestion_level(asc),
            "updated_at": datetime.now(JST).isoformat(),
        })
    return result


async def get_current_by_route(db: AsyncSession) -> list[dict]:
    """Get current congestion for all routes."""
    today = date.today()
    routes = (await db.execute(
        select(Route).order_by(Route.sort_order)
    )).scalars().all()

    result = []
    for route in routes:
        rt = (await db.execute(
            select(RouteRealtime)
            .where(RouteRealtime.route_id == route.id, RouteRealtime.date == today)
        )).scalars().first()

        asc = rt.ascending_count if rt else 0
        desc = rt.descending_count if rt else 0
        level = rt.congestion_level if rt else "low"

        result.append({
            "route_id": str(route.id),
            "route_name": route.name,
            "ascending_count": asc,
            "descending_count": desc,
            "on_mountain": max(asc - desc, 0),
            "congestion_level": level,
            "usage_percentage": float(route.usage_percentage) if route.usage_percentage else None,
        })
    return result


async def get_hourly(db: AsyncSession, target_date: date, location_id: str = None) -> list[dict]:
    """Get hourly counts for a given date."""
    query = select(HourlyCount).where(HourlyCount.date == target_date)
    if location_id:
        query = query.where(HourlyCount.location_id == location_id)
    query = query.order_by(HourlyCount.hour)

    rows = (await db.execute(query)).scalars().all()
    return [{
        "hour": r.hour,
        "ascending": r.ascending,
        "descending": r.descending,
        "cumulative_ascending": r.cumulative_ascending,
        "cumulative_descending": r.cumulative_descending,
    } for r in rows]


async def get_forecast_calendar(db: AsyncSession) -> list[dict]:
    """Generate 14-day congestion forecast based on historical day-of-week averages."""
    # Get day-of-week averages from historical data
    dow_avgs = await _get_dow_averages(db)
    today = date.today()
    days = []
    for i in range(14):
        d = today + timedelta(days=i)
        dow = d.weekday()
        predicted = dow_avgs.get(dow, 100)
        days.append({
            "date": d.isoformat(),
            "day_of_week": DOW_JA[dow],
            "predicted_count": predicted,
            "congestion_level": congestion_level(predicted),
            "weather_code": None,
        })
    return days


async def get_forecast_dow(db: AsyncSession) -> list[dict]:
    """Get average visitor count by day of week."""
    dow_avgs = await _get_dow_averages(db)
    return [
        {"day_of_week": DOW_JA[i], "average_count": dow_avgs.get(i, 0)}
        for i in range(7)
    ]


async def _get_dow_averages(db: AsyncSession) -> dict[int, int]:
    """Calculate day-of-week averages from hourly_counts."""
    rows = (await db.execute(
        select(
            func.extract("dow", HourlyCount.date).label("dow"),
            func.sum(HourlyCount.ascending).label("total"),
            func.count(func.distinct(HourlyCount.date)).label("days"),
        )
        .group_by("dow")
    )).all()

    result = {}
    for row in rows:
        dow_pg = int(row.dow)  # PostgreSQL: 0=Sunday
        dow_py = (dow_pg - 1) % 7  # Python: 0=Monday
        avg_count = int(row.total / row.days) if row.days > 0 else 0
        result[dow_py] = avg_count

    # Defaults if no data
    defaults = {0: 95, 1: 78, 2: 82, 3: 88, 4: 110, 5: 285, 6: 242}
    for i in range(7):
        if i not in result:
            result[i] = defaults[i]

    return result

"""Admin API router - 15 endpoints (JWT auth required)."""

import uuid
from datetime import date, datetime, timezone
from typing import Optional
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.models import (
    Device, Location, Alert, CalibrationFactor, CalibrationRecord,
    CameraImage, CameraAnalysis, HourlyCount, SensorCount,
    TrailStatus, Route, DeviceStatusLog,
)
from app.schemas.admin import (
    DeviceItem, DeviceUpdateRequest, CalibrationFactorItem, CalibrationFactorUpdate,
    CalibrationRecordItem, CalibrationRecordCreate, CameraAnalysisItem,
    SiteAnalysisItem, TrailStatusCreate, TrailStatusUpdate,
    AlertCreate, AlertUpdate, AlertSummary, DashboardResponse, DashboardSummary,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------- GET /admin/dashboard ----------
@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """ダッシュボード集計データ"""
    today = date.today()

    # Summary: total ascending/descending from hourly_counts
    agg = (await db.execute(
        select(
            func.coalesce(func.sum(HourlyCount.ascending), 0).label("total_asc"),
            func.coalesce(func.sum(HourlyCount.descending), 0).label("total_desc"),
        ).where(HourlyCount.date == today)
    )).one()
    total_asc, total_desc = int(agg.total_asc), int(agg.total_desc)

    # Device uptime
    total_devices = (await db.execute(select(func.count(Device.id)))).scalar() or 0
    active_devices = (await db.execute(
        select(func.count(Device.id)).where(Device.status == "active")
    )).scalar() or 0
    uptime = round((active_devices / total_devices * 100), 1) if total_devices > 0 else 0

    # Recent alerts
    alerts_rows = (await db.execute(
        select(Alert).order_by(Alert.created_at.desc()).limit(10)
    )).scalars().all()
    alerts = [AlertSummary(
        id=str(a.id), alert_type=a.alert_type, title=a.title,
        message=a.message, value=float(a.value) if a.value else None,
        threshold=float(a.threshold) if a.threshold else None,
        is_read=a.is_read, created_at=a.created_at,
    ) for a in alerts_rows]

    # Hourly data for chart
    hourly_rows = (await db.execute(
        select(HourlyCount).where(HourlyCount.date == today).order_by(HourlyCount.hour)
    )).scalars().all()
    hourly = [{"hour": h.hour, "ascending": h.ascending, "descending": h.descending} for h in hourly_rows]

    # Route breakdown
    from app.services.congestion import get_current_by_route
    routes = await get_current_by_route(db)

    return DashboardResponse(
        summary=DashboardSummary(
            total_ascending=total_asc, total_descending=total_desc,
            on_mountain=max(total_asc - total_desc, 0),
            device_uptime_pct=uptime,
        ),
        alerts=alerts,
        hourly=hourly,
        route_breakdown=routes,
    )


# ---------- GET /admin/history ----------
@router.get("/history")
async def get_history(
    year: Optional[int] = Query(None),
    location_id: Optional[str] = Query(None),
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """過去データ分析"""
    query = select(HourlyCount)
    if year:
        query = query.where(func.extract("year", HourlyCount.date) == year)
    if location_id:
        query = query.where(HourlyCount.location_id == location_id)

    rows = (await db.execute(query.order_by(HourlyCount.date, HourlyCount.hour))).scalars().all()

    # Aggregate by granularity
    data = {}
    for r in rows:
        if granularity == "day":
            key = r.date.isoformat()
        elif granularity == "week":
            key = f"{r.date.isocalendar()[0]}-W{r.date.isocalendar()[1]:02d}"
        else:
            key = f"{r.date.year}-{r.date.month:02d}"
        if key not in data:
            data[key] = {"period": key, "ascending": 0, "descending": 0}
        data[key]["ascending"] += r.ascending
        data[key]["descending"] += r.descending

    return {"granularity": granularity, "data": list(data.values())}


# ---------- GET /admin/devices ----------
@router.get("/devices")
async def get_devices(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """デバイス管理一覧"""
    rows = (await db.execute(
        select(Device, Location.name.label("loc_name"))
        .join(Location, Device.location_id == Location.id)
        .order_by(Device.device_id)
    )).all()
    return {"devices": [DeviceItem(
        id=str(d.id), device_id=d.device_id, location_name=loc_name,
        device_type=d.device_type, status=d.status, battery_pct=d.battery_pct,
        temperature_c=float(d.temperature_c) if d.temperature_c else None,
        last_data_at=d.last_data_at, last_heartbeat=d.last_heartbeat,
        maintenance_notes=d.maintenance_notes,
    ) for d, loc_name in rows]}


# ---------- PATCH /admin/devices/:id ----------
@router.patch("/devices/{device_id}")
async def update_device(
    device_id: str,
    body: DeviceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """デバイスのステータス・備考を更新"""
    device = (await db.execute(
        select(Device).where(Device.device_id == device_id)
    )).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="デバイスが見つかりません")

    old_status = device.status
    if body.status:
        device.status = body.status
    if body.maintenance_notes is not None:
        device.maintenance_notes = body.maintenance_notes

    # Log status change
    if body.status and body.status != old_status:
        log = DeviceStatusLog(
            device_id_fk=device.device_id, previous_status=old_status,
            new_status=body.status, battery_pct=device.battery_pct,
            changed_by=user.get("email", "admin"), reason=body.maintenance_notes,
        )
        db.add(log)

    await db.flush()
    return {"status": "updated", "device_id": str(device.id)}


# ---------- GET /admin/calibration/factors ----------
@router.get("/calibration/factors")
async def get_calibration_factors(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """天候別補正係数テーブル"""
    rows = (await db.execute(
        select(CalibrationFactor, Location.name.label("loc_name"))
        .join(Location, CalibrationFactor.location_id == Location.id)
        .order_by(Location.name, CalibrationFactor.weather)
    )).all()
    return {"factors": [CalibrationFactorItem(
        id=str(f.id), location_name=loc_name, weather=f.weather,
        ascending_factor=float(f.ascending_factor),
        descending_factor=float(f.descending_factor),
        sample_days=f.sample_days, confidence_pct=f.confidence_pct,
        valid_from=f.valid_from, valid_to=f.valid_to,
    ) for f, loc_name in rows]}


# ---------- PUT /admin/calibration/factors/:id ----------
@router.put("/calibration/factors/{factor_id}")
async def update_calibration_factor(
    factor_id: str,
    body: CalibrationFactorUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """補正係数の手動調整"""
    factor = (await db.execute(
        select(CalibrationFactor).where(CalibrationFactor.id == factor_id)
    )).scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="補正係数が見つかりません")
    if body.ascending_factor is not None:
        factor.ascending_factor = body.ascending_factor
    if body.descending_factor is not None:
        factor.descending_factor = body.descending_factor
    if body.valid_from is not None:
        factor.valid_from = body.valid_from
    if body.valid_to is not None:
        factor.valid_to = body.valid_to
    await db.flush()
    return {"status": "updated"}


# ---------- GET /admin/calibration/records ----------
@router.get("/calibration/records")
async def get_calibration_records(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """キャリブレーション記録一覧"""
    total = (await db.execute(select(func.count(CalibrationRecord.id)))).scalar()
    rows = (await db.execute(
        select(CalibrationRecord, Location.name.label("loc_name"))
        .join(Location, CalibrationRecord.location_id == Location.id)
        .order_by(CalibrationRecord.created_at.desc())
        .limit(limit).offset(offset)
    )).all()
    return {"total": total, "limit": limit, "offset": offset, "items": [
        CalibrationRecordItem(
            id=str(r.id), location_name=loc_name, date=r.date,
            time_slot=r.time_slot, weather=r.weather,
            manual_ascending=r.manual_ascending, manual_descending=r.manual_descending,
            ir_ascending=r.ir_ascending, ir_descending=r.ir_descending,
            correction_factor=float(r.correction_factor) if r.correction_factor else None,
            operator=r.operator,
        ) for r, loc_name in rows
    ]}


# ---------- POST /admin/calibration/records ----------
@router.post("/calibration/records", status_code=201)
async def create_calibration_record(
    body: CalibrationRecordCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """キャリブレーション記録登録"""
    # Calculate correction factor
    correction = None
    # Auto-fetch IR counts could be added here

    record = CalibrationRecord(
        location_id=body.location_id, date=body.date, time_slot=body.time_slot,
        weather=body.weather, manual_ascending=body.manual_ascending,
        manual_descending=body.manual_descending,
        correction_factor=correction, operator=body.operator or user.get("email"),
    )
    db.add(record)
    await db.flush()
    return {"id": str(record.id), "status": "created"}


# ---------- GET /admin/camera-analysis ----------
@router.get("/camera-analysis")
async def get_camera_analysis(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """カメラAI解析結果一覧"""
    total = (await db.execute(select(func.count(CameraAnalysis.id)))).scalar()
    rows = (await db.execute(
        select(CameraAnalysis, CameraImage.camera_id, CameraImage.capture_timestamp)
        .join(CameraImage, CameraAnalysis.image_id == CameraImage.id)
        .order_by(CameraImage.capture_timestamp.desc())
        .limit(limit).offset(offset)
    )).all()
    return {"total": total, "items": [
        CameraAnalysisItem(
            id=str(ca.id), camera_id=cam_id,
            capture_timestamp=capture_ts,
            detected_person_count=ca.detected_person_count,
            group_count=ca.group_count, ir_count_at_time=ca.ir_count_at_time,
            confidence_score=float(ca.confidence_score) if ca.confidence_score else None,
            correction_suggestion=ca.correction_suggestion,
        ) for ca, cam_id, capture_ts in rows
    ]}


# ---------- GET /admin/site-analysis ----------
@router.get("/site-analysis")
async def get_site_analysis(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """設置場所分析（locations × devices JOIN）"""
    rows = (await db.execute(
        select(
            Location.name, Location.prefecture,
            Device.device_type, Device.status, Device.last_data_at,
            func.count(Device.id).label("device_count"),
        )
        .join(Device, Device.location_id == Location.id)
        .group_by(Location.name, Location.prefecture, Device.device_type, Device.status, Device.last_data_at)
        .order_by(Location.name)
    )).all()

    total_devices = sum(r.device_count for r in rows)
    active_devices = sum(r.device_count for r in rows if r.status == "active")
    sites = [SiteAnalysisItem(
        location_name=r.name, prefecture=r.prefecture,
        device_type=r.device_type, device_count=r.device_count,
        active_count=r.device_count if r.status == "active" else 0,
        last_data_at=r.last_data_at,
    ) for r in rows]

    return {
        "total_locations": len(set(r.name for r in rows)),
        "active_devices": active_devices,
        "total_devices": total_devices,
        "avg_uptime_pct": round(active_devices / total_devices * 100, 1) if total_devices else 0,
        "sites": sites,
    }


# ---------- GET /admin/export/:type ----------
@router.get("/export/{export_type}")
async def export_csv(
    export_type: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """CSV/Excelエクスポート"""
    import csv
    import io

    if export_type == "calibration":
        rows = (await db.execute(
            select(CalibrationRecord, Location.name.label("loc"))
            .join(Location, CalibrationRecord.location_id == Location.id)
            .order_by(CalibrationRecord.date.desc())
        )).all()
        headers = ["date", "location", "time_slot", "weather", "manual_asc", "manual_desc", "ir_asc", "ir_desc", "correction", "operator"]
        data = [[str(r.date), loc, r.time_slot, r.weather, r.manual_ascending, r.manual_descending, r.ir_ascending, r.ir_descending, r.correction_factor, r.operator] for r, loc in rows]
    elif export_type == "camera":
        rows = (await db.execute(
            select(CameraAnalysis, CameraImage.camera_id, CameraImage.capture_timestamp)
            .join(CameraImage, CameraAnalysis.image_id == CameraImage.id)
        )).all()
        headers = ["timestamp", "camera", "ai_count", "group_count", "ir_count", "confidence", "suggestion"]
        data = [[str(ts), cam, ca.detected_person_count, ca.group_count, ca.ir_count_at_time, ca.confidence_score, ca.correction_suggestion] for ca, cam, ts in rows]
    elif export_type == "site":
        rows = (await db.execute(
            select(Device, Location.name.label("loc"), Location.prefecture)
            .join(Location, Device.location_id == Location.id)
        )).all()
        headers = ["location", "prefecture", "device_id", "type", "status", "battery", "last_data"]
        data = [[loc, pref, d.device_id, d.device_type, d.status, d.battery_pct, str(d.last_data_at) if d.last_data_at else ""] for d, loc, pref in rows]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown export type: {export_type}")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(data)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={export_type}_export.csv"},
    )


# ---------- POST /admin/trail-status ----------
@router.post("/trail-status", status_code=201)
async def create_trail_status(
    body: TrailStatusCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ts = TrailStatus(
        route_id=body.route_id, status_type=body.status_type,
        title=body.title, description=body.description, source=body.source,
    )
    db.add(ts)
    await db.flush()
    return {"id": str(ts.id), "status": "created"}


# ---------- PUT /admin/trail-status/:id ----------
@router.put("/trail-status/{status_id}")
async def update_trail_status(
    status_id: str,
    body: TrailStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ts = (await db.execute(select(TrailStatus).where(TrailStatus.id == status_id))).scalar_one_or_none()
    if not ts:
        raise HTTPException(status_code=404, detail="登山道状況が見つかりません")
    for field in ["status_type", "title", "description", "source", "is_active"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(ts, field, val)
    ts.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "updated"}


# ---------- DELETE /admin/trail-status/:id ----------
@router.delete("/trail-status/{status_id}")
async def delete_trail_status(
    status_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """論理削除: is_active=false"""
    ts = (await db.execute(select(TrailStatus).where(TrailStatus.id == status_id))).scalar_one_or_none()
    if not ts:
        raise HTTPException(status_code=404, detail="登山道状況が見つかりません")
    ts.is_active = False
    ts.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "deleted (soft)"}


# ---------- POST /admin/alerts ----------
@router.post("/alerts", status_code=201)
async def create_alert(
    body: AlertCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    alert = Alert(
        alert_type=body.alert_type, location_id=body.location_id,
        title=body.title, message=body.message,
    )
    db.add(alert)
    await db.flush()
    return {"id": str(alert.id), "status": "created"}


# ---------- PATCH /admin/alerts/:id ----------
@router.patch("/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    body: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="アラートが見つかりません")
    if body.is_read is not None:
        alert.is_read = body.is_read
    if body.message is not None:
        alert.message = body.message
    await db.flush()
    return {"status": "updated"}

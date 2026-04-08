"""Device API router - 2 endpoints (API key auth)."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import verify_device_api_key
from app.models import Device, SensorCount, CameraImage
from app.schemas.device import SensorCountCreate, SensorCountResponse, CameraUploadResponse
from app.services.camera_adapter import get_camera_adapter

router = APIRouter(prefix="/api/v1", tags=["device"])


# --- POST /sensor/count ---
@router.post("/sensor/count", response_model=SensorCountResponse, status_code=201)
async def receive_sensor_count(
    body: SensorCountCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_device_api_key),
):
    """IRセンサーデータ受信（1時間バッチ）"""
    # Validate device exists
    device = (await db.execute(
        select(Device).where(Device.device_id == body.device_id)
    )).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail=f"デバイス {body.device_id} が見つかりません")

    # Create sensor count record
    record = SensorCount(
        device_id=body.device_id,
        location_id=device.location_id,
        timestamp=body.timestamp,
        up_count=body.up_count,
        down_count=body.down_count,
        battery_pct=body.battery_pct,
        temperature_c=body.temperature_c,
    )
    db.add(record)

    # Update device status
    device.last_data_at = body.timestamp
    device.last_heartbeat = datetime.now(timezone.utc)
    if body.battery_pct is not None:
        device.battery_pct = body.battery_pct
    if body.temperature_c is not None:
        device.temperature_c = body.temperature_c

    await db.flush()

    return SensorCountResponse(
        id=str(record.id),
        device_id=body.device_id,
        location_id=str(device.location_id),
        timestamp=body.timestamp,
    )


# --- POST /camera/upload ---
@router.post("/camera/upload", response_model=CameraUploadResponse, status_code=201)
async def upload_camera_image(
    camera_id: str = Form(...),
    timestamp: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_device_api_key),
):
    """カメラ画像アップロード"""
    # Validate device
    device = (await db.execute(
        select(Device).where(Device.device_id == camera_id)
    )).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail=f"カメラ {camera_id} が見つかりません")

    # Read file
    image_data = await file.read()
    file_size = len(image_data)

    # Storage path (in production: upload to Supabase Storage)
    capture_ts = datetime.fromisoformat(timestamp)
    storage_path = f"camera/{camera_id}/{capture_ts.strftime('%Y%m%d_%H%M%S')}.jpg"

    # TODO: Upload to Supabase Storage
    # For now, store path reference only
    # from supabase import create_client
    # supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    # supabase.storage.from_("camera-images").upload(storage_path, image_data)

    record = CameraImage(
        camera_id=camera_id,
        capture_timestamp=capture_ts,
        storage_path=storage_path,
        file_size_bytes=file_size,
        analysis_status="pending",
    )
    db.add(record)

    # Update device heartbeat
    device.last_data_at = capture_ts
    device.last_heartbeat = datetime.now(timezone.utc)

    await db.flush()

    return CameraUploadResponse(
        id=str(record.id),
        camera_id=camera_id,
        storage_path=storage_path,
    )

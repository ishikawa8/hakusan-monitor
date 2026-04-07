"""AI analysis background worker (design doc 6.1 flow)."""

import logging
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models import CameraImage, CameraAnalysis, SensorCount
from app.services.ai_analyzer import get_analyzer, DetectionResult
from app.config import get_settings

logger = logging.getLogger(__name__)


async def process_pending_images():
    """Process all pending camera images through AI analysis.

    Flow per design doc 6.1:
    1. Get camera_images with analysis_status='pending'
    2. Download image from storage_path
    3. Set status to 'processing'
    4. Run Detectron2 person detection + group clustering
    5. Save results to camera_analyses
    6. Set status to 'completed' or 'failed'
    """
    settings = get_settings()
    analyzer = get_analyzer(
        confidence_threshold=settings.ai_confidence_threshold
    )

    async with async_session() as db:
        # Step 1: Get pending images
        pending = (await db.execute(
            select(CameraImage)
            .where(CameraImage.analysis_status == "pending")
            .order_by(CameraImage.created_at)
            .limit(10)
        )).scalars().all()

        if not pending:
            return 0

        processed = 0
        for image in pending:
            try:
                # Step 3: Set to processing
                image.analysis_status = "processing"
                await db.commit()

                # Step 2: Download image
                # In production: download from Supabase Storage
                # image_bytes = supabase.storage.from_("camera-images").download(image.storage_path)
                # For now, use mock analysis
                image_bytes = b""  # Mock

                # Step 4: Run detection
                result: DetectionResult = analyzer.analyze(image_bytes)

                # Get IR count at same time for comparison
                ir_count = await _get_ir_count_at_time(db, image.camera_id, image.capture_timestamp)

                # Generate correction suggestion
                suggestion = None
                if ir_count is not None and result.person_count > 0:
                    diff = result.person_count - ir_count
                    if abs(diff) >= 2:
                        suggestion = f"グループ補正{'+' if diff > 0 else ''}{diff}"

                # Step 5: Save results
                analysis = CameraAnalysis(
                    image_id=image.id,
                    detected_person_count=result.person_count,
                    group_count=result.group_count,
                    group_composition=result.group_composition,
                    ir_count_at_time=ir_count,
                    confidence_score=result.confidence_score,
                    correction_suggestion=suggestion,
                    raw_metadata=result.raw_metadata,
                )
                db.add(analysis)

                # Step 6: Set completed
                image.analysis_status = "completed"
                await db.commit()
                processed += 1
                logger.info(f"Analyzed image {image.id}: {result.person_count} persons, {result.group_count} groups")

            except Exception as e:
                logger.error(f"Failed to analyze image {image.id}: {e}")
                image.analysis_status = "failed"
                await db.commit()

        return processed


async def _get_ir_count_at_time(db: AsyncSession, camera_id: str, timestamp: datetime) -> int | None:
    """Get IR sensor count closest to camera capture time."""
    from sqlalchemy import func

    # Find the device location for this camera
    from app.models import Device
    device = (await db.execute(
        select(Device).where(Device.device_id == camera_id)
    )).scalar_one_or_none()
    if not device:
        return None

    # Get the closest sensor count within 1 hour
    from datetime import timedelta
    result = (await db.execute(
        select(func.sum(SensorCount.up_count + SensorCount.down_count))
        .where(
            SensorCount.location_id == device.location_id,
            SensorCount.timestamp.between(
                timestamp - timedelta(hours=1),
                timestamp + timedelta(hours=1),
            ),
        )
    )).scalar()

    return int(result) if result else None

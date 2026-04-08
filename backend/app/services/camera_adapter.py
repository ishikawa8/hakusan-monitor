"""Camera Adapter pattern (design doc 4.5, 11.1).

Abstraction layer for camera-agnostic image ingestion.
Camera tool is TBD - this provides the interface contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CameraEvent:
    """Unified camera event after adapter parsing."""
    camera_id: str
    capture_timestamp: datetime
    image_bytes: bytes
    file_size: int
    metadata: dict


@dataclass
class DeviceStatus:
    """Device status from camera heartbeat."""
    camera_id: str
    battery_pct: Optional[int]
    temperature_c: Optional[float]
    signal_strength: Optional[int]
    timestamp: datetime


class BaseCameraAdapter(ABC):
    """Abstract base class for camera adapters.

    When the camera tool is decided, implement a concrete adapter:
      class HykeCamera(BaseCameraAdapter): ...
    """

    @abstractmethod
    def parse_payload(self, raw_data: dict) -> CameraEvent:
        """Parse raw camera payload into unified CameraEvent."""
        ...

    @abstractmethod
    def extract_image(self, raw_data: dict) -> bytes:
        """Extract image bytes from raw payload."""
        ...

    @abstractmethod
    def get_device_status(self, raw_data: dict) -> DeviceStatus:
        """Extract device status from raw payload."""
        ...


class GenericCameraAdapter(BaseCameraAdapter):
    """Default adapter for testing / development.

    Expects JSON payload: {
        "camera_id": "...",
        "timestamp": "ISO8601",
        "image_base64": "...",
        "battery_pct": 75,
        "temperature_c": 18.5
    }
    """

    def parse_payload(self, raw_data: dict) -> CameraEvent:
        import base64
        image_bytes = base64.b64decode(raw_data.get("image_base64", ""))
        return CameraEvent(
            camera_id=raw_data["camera_id"],
            capture_timestamp=datetime.fromisoformat(raw_data["timestamp"]),
            image_bytes=image_bytes,
            file_size=len(image_bytes),
            metadata=raw_data.get("metadata", {}),
        )

    def extract_image(self, raw_data: dict) -> bytes:
        import base64
        return base64.b64decode(raw_data.get("image_base64", ""))

    def get_device_status(self, raw_data: dict) -> DeviceStatus:
        return DeviceStatus(
            camera_id=raw_data["camera_id"],
            battery_pct=raw_data.get("battery_pct"),
            temperature_c=raw_data.get("temperature_c"),
            signal_strength=raw_data.get("signal_strength"),
            timestamp=datetime.fromisoformat(raw_data.get("timestamp", datetime.now(timezone.utc).isoformat())),
        )


def get_camera_adapter(adapter_type: str = "generic") -> BaseCameraAdapter:
    """Factory: returns adapter instance by type."""
    adapters = {
        "generic": GenericCameraAdapter,
    }
    cls = adapters.get(adapter_type, GenericCameraAdapter)
    return cls()

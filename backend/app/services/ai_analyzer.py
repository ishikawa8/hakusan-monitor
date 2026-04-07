"""AI image analysis module using Detectron2 (design doc Chapter 6).

Processing flow:
1. Get camera_images with analysis_status='pending'
2. Download image from storage_path
3. Set status to 'processing'
4. Run Detectron2 person detection + group clustering
5. Save results to camera_analyses
6. Set status to 'completed' or 'failed'
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    person_count: int
    group_count: int
    group_composition: list[dict]  # [{"size": 3}, {"size": 2}]
    confidence_score: float
    raw_metadata: dict


class BaseAnalyzer(ABC):
    """Abstract base for AI analyzers (design doc 11.1)."""

    @abstractmethod
    def analyze(self, image_bytes: bytes) -> DetectionResult:
        ...


class Detectron2Analyzer(BaseAnalyzer):
    """Person detection using Detectron2 (Apache 2.0).

    Requires:
        pip install detectron2 (from source or pre-built wheel)
    """

    def __init__(self, config_path: str = None, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self._predictor = None
        self._config_path = config_path

    def _load_model(self):
        """Lazy-load Detectron2 model."""
        if self._predictor is not None:
            return

        try:
            from detectron2 import model_zoo
            from detectron2.config import get_cfg
            from detectron2.engine import DefaultPredictor

            cfg = get_cfg()
            cfg.merge_from_file(
                model_zoo.get_config_file("COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml")
            )
            cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = self.confidence_threshold
            cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url(
                "COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml"
            )
            cfg.MODEL.DEVICE = "cpu"  # Use GPU if available: "cuda"
            self._predictor = DefaultPredictor(cfg)
            logger.info("Detectron2 model loaded successfully")
        except ImportError:
            logger.warning("Detectron2 not installed. Using mock analyzer.")
            self._predictor = "mock"

    def analyze(self, image_bytes: bytes) -> DetectionResult:
        self._load_model()

        if self._predictor == "mock":
            return self._mock_analyze()

        import cv2
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Failed to decode image")

        outputs = self._predictor(image)
        instances = outputs["instances"]

        # Filter for person class (COCO class 0)
        person_mask = instances.pred_classes == 0
        person_boxes = instances.pred_boxes[person_mask]
        person_scores = instances.scores[person_mask]

        person_count = len(person_boxes)
        avg_confidence = float(person_scores.mean()) if person_count > 0 else 0.0

        # Group clustering by spatial proximity
        groups = self._cluster_groups(person_boxes.tensor.cpu().numpy()) if person_count > 0 else []

        return DetectionResult(
            person_count=person_count,
            group_count=len(groups),
            group_composition=[{"size": len(g)} for g in groups],
            confidence_score=round(avg_confidence, 3),
            raw_metadata={
                "model": "faster_rcnn_R_50_FPN_3x",
                "threshold": self.confidence_threshold,
                "image_size": list(image.shape[:2]),
            },
        )

    def _cluster_groups(self, boxes: np.ndarray, distance_threshold: float = 100.0) -> list[list[int]]:
        """Simple spatial clustering of detected persons into groups."""
        if len(boxes) == 0:
            return []

        # Calculate centers
        centers = np.stack([(boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2], axis=1)

        visited = set()
        groups = []

        for i in range(len(centers)):
            if i in visited:
                continue
            group = [i]
            visited.add(i)
            queue = [i]
            while queue:
                current = queue.pop(0)
                for j in range(len(centers)):
                    if j in visited:
                        continue
                    dist = np.linalg.norm(centers[current] - centers[j])
                    if dist < distance_threshold:
                        group.append(j)
                        visited.add(j)
                        queue.append(j)
            groups.append(group)

        return groups

    def _mock_analyze(self) -> DetectionResult:
        """Mock analysis for testing without Detectron2."""
        import random
        count = random.randint(1, 8)
        groups = []
        remaining = count
        while remaining > 0:
            size = min(random.randint(1, 3), remaining)
            groups.append({"size": size})
            remaining -= size

        return DetectionResult(
            person_count=count,
            group_count=len(groups),
            group_composition=groups,
            confidence_score=round(random.uniform(0.7, 0.95), 3),
            raw_metadata={"model": "mock", "note": "Detectron2 not installed"},
        )


def get_analyzer(analyzer_type: str = "detectron2", **kwargs) -> BaseAnalyzer:
    """Factory: returns analyzer instance."""
    analyzers = {
        "detectron2": Detectron2Analyzer,
    }
    cls = analyzers.get(analyzer_type, Detectron2Analyzer)
    return cls(**kwargs)

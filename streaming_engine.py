"""
Real-Time Streaming Recognition Engine with Temporal Stabilization.
Optimized for continuous video frames from Android CameraX streaming.
"""
import time
from collections import deque
from typing import Dict, List, Optional
import cv2
import numpy as np

from pipeline import ContainerRecognitionPipeline
from container_parser import validate_container_number


class TemporalStabilizer:
    """
    Maintains a rolling window of recognized container codes across video frames
    to prevent flickering and lock onto valid container numbers.
    """
    def __init__(self, window_size: int = 4):
        self.window_size = window_size
        self.history = deque(maxlen=window_size)
        self.locked_code = None
        self.locked_meta = None
        self.lock_count = 0

    def update(self, current_res: Dict) -> Dict:
        code = current_res.get("container_number")
        is_val = current_res.get("is_valid", False)

        if code and code != "Not Found":
            self.history.append((code, is_val, current_res))
        else:
            self.history.append((None, False, None))

        # Count frequencies in recent frames
        code_counts = {}
        for c, v, meta in self.history:
            if c:
                code_counts[c] = code_counts.get(c, 0) + 1

        # Check for stable code
        best_code = None
        max_freq = 0
        for c, count in code_counts.items():
            if count > max_freq:
                max_freq = count
                best_code = c

        if best_code:
            # Find the best metadata for this code
            for c, v, meta in reversed(self.history):
                if c == best_code and meta:
                    result = dict(meta)
                    if max_freq >= 2 and v:
                        result["stream_status"] = "LOCKED"
                        result["confidence_level"] = "HIGH"
                    else:
                        result["stream_status"] = "TRACKING"
                        result["confidence_level"] = "MEDIUM"
                    return result

        current_res["stream_status"] = "SEARCHING"
        current_res["confidence_level"] = "LOW"
        return current_res


class StreamingRecognitionEngine:
    def __init__(self, model_path: str = "weights/container_detector.pt"):
        self.pipeline = ContainerRecognitionPipeline(model_path)
        self.stabilizer = TemporalStabilizer(window_size=4)
        self.frame_count = 0
        self.last_timestamp = time.time()
        self.fps = 0.0

    def process_frame_bytes(self, image_bytes: bytes, conf_threshold: float = 0.20) -> Dict:
        """
        Decodes incoming streaming JPEG bytes and runs optimized pipeline.
        """
        t0 = time.time()
        self.frame_count += 1

        # Calculate live FPS
        dt = t0 - self.last_timestamp
        if dt > 0.5:
            self.fps = round(self.frame_count / dt, 1)
            self.frame_count = 0
            self.last_timestamp = t0

        # Decode JPEG bytes in memory (zero disk I/O)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"status": "error", "message": "Failed to decode frame"}

        h, w = img.shape[:2]

        # Fast detection & recognition
        res = self.pipeline.process(
            img,
            conf_threshold=conf_threshold,
            use_detector=True,
            crop_padding=0.08
        )

        # Apply temporal smoothing
        smoothed = self.stabilizer.update(res)

        # Format lightweight JSON output for Android app
        box = None
        if smoothed.get("detected_regions"):
            box = smoothed["detected_regions"][0]["box"]
        elif smoothed.get("selected_crop_box"):
            box = smoothed["selected_crop_box"]

        output = {
            "stream_status": smoothed.get("stream_status", "SEARCHING"),
            "confidence_level": smoothed.get("confidence_level", "LOW"),
            "container_number": smoothed.get("container_number", ""),
            "formatted_number": smoothed.get("formatted_number", ""),
            "is_valid": smoothed.get("is_valid", False),
            "repaired": smoothed.get("repaired", False),
            "owner_code": smoothed.get("owner_code", ""),
            "owner_name": smoothed.get("owner_name", ""),
            "category_desc": smoothed.get("category_description", ""),
            "size_type": smoothed.get("size_type_code", ""),
            "size_type_desc": smoothed.get("size_type_desc", ""),
            "check_digit": smoothed.get("check_digit", ""),
            "expected_check_digit": smoothed.get("expected_check_digit", ""),
            "box": box,  # [x1, y1, x2, y2]
            "frame_width": w,
            "frame_height": h,
            "latency_ms": smoothed.get("elapsed_time_ms", round((time.time() - t0) * 1000, 1)),
            "fps": self.fps
        }
        return output

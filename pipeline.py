"""
End-to-End Container Number Recognition Pipeline.
Combines YOLO Container Region Detection with RapidOCR and ISO 6346 Validation.
"""
import os
import time
import cv2
import numpy as np
from PIL import Image
from typing import Dict, List, Optional, Tuple, Union
from ultralytics import YOLO

from container_parser import (
    calculate_check_digit,
    validate_container_number,
    extract_iso_candidates,
    parse_container_info,
    OWNER_CODES,
    SIZE_TYPE_CODES
)
from ocr_engine import ContainerOCREngine


class ContainerRecognitionPipeline:
    def __init__(self, yolo_model_path: Optional[str] = None):
        # Locate YOLO model weights
        default_weights = [
            "models/container_detector/weights/best.pt",
            "models/container_detector/weights/last.pt",
            "runs/detect/container_detector/weights/best.pt",
            "runs/detect/container_detector/weights/last.pt",
            "yolo11n.pt"
        ]

        self.model_path = None
        if yolo_model_path and os.path.exists(yolo_model_path):
            self.model_path = yolo_model_path
        else:
            for p in default_weights:
                if os.path.exists(p):
                    self.model_path = p
                    break

        self.yolo = None
        if self.model_path:
            try:
                self.yolo = YOLO(self.model_path)
            except Exception as e:
                print(f"Warning: Failed to load YOLO from {self.model_path}: {e}")

        # OCR Engine
        self.ocr = ContainerOCREngine()

    def reload_yolo(self, model_path: str):
        """Reloads or switches the YOLO model checkpoint."""
        if os.path.exists(model_path):
            self.model_path = model_path
            self.yolo = YOLO(model_path)
            return True
        return False

    def detect_regions(self, image: np.ndarray, conf: float = 0.25) -> List[Dict]:
        """
        Runs YOLO to detect container code panel regions.
        Returns list of {'box': [x1, y1, x2, y2], 'confidence': float, 'class_id': int}
        """
        if self.yolo is None:
            return []

        h, w = image.shape[:2]
        results = self.yolo.predict(image, conf=conf, verbose=False)
        regions = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for b in boxes:
                xyxy = b.xyxy[0].cpu().numpy().astype(int)
                score = float(b.conf[0].cpu().numpy())
                cls_id = int(b.cls[0].cpu().numpy())
                x1, y1, x2, y2 = max(0, xyxy[0]), max(0, xyxy[1]), min(w, xyxy[2]), min(h, xyxy[3])
                regions.append({
                    "box": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": score,
                    "class_id": cls_id
                })
        # Sort by confidence descending
        regions.sort(key=lambda r: r["confidence"], reverse=True)
        return regions

    def process(
        self,
        image_input: Union[str, np.ndarray, Image.Image],
        conf_threshold: float = 0.25,
        use_detector: bool = True,
        crop_padding: float = 0.08
    ) -> Dict:
        """
        Processes an image to detect and recognize the container number.
        Returns structured analysis result.
        """
        t0 = time.time()

        # Load image into numpy BGR array
        if isinstance(image_input, str):
            image = cv2.imread(image_input)
            if image is None:
                raise ValueError(f"Could not load image from path: {image_input}")
        elif isinstance(image_input, Image.Image):
            rgb = np.array(image_input)
            image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, np.ndarray):
            image = image_input.copy()
        else:
            raise TypeError("Unsupported image_input type")

        img_h, img_w = image.shape[:2]
        all_ocr_texts = []
        all_ocr_detections = []
        detected_regions = []
        selected_crop_box = None

        # 1. Detection Stage
        if use_detector and self.yolo is not None:
            detected_regions = self.detect_regions(image, conf=conf_threshold)

        # 2. OCR Stage
        candidates = []

        # If container regions were detected, crop and run OCR on them first
        if detected_regions:
            for region in detected_regions:
                rx1, ry1, rx2, ry3 = region["box"]
                bw, bh = rx2 - rx1, ry3 - ry1
                
                # Add padding
                pad_x = int(bw * crop_padding)
                pad_y = int(bh * crop_padding)
                cx1 = max(0, rx1 - pad_x)
                cy1 = max(0, ry1 - pad_y)
                cx2 = min(img_w, rx2 + pad_x)
                cy2 = min(img_h, ry3 + pad_y)

                crop = image[cy1:cy2, cx1:cx2]
                if crop.size == 0:
                    continue

                crop_texts, crop_dets = self.ocr.extract_texts_multipass(crop)
                # Map bounding boxes back to original image space
                for d in crop_dets:
                    shifted_box = [[pt[0] + cx1, pt[1] + cy1] for pt in d["box"]]
                    all_ocr_detections.append({
                        "box": shifted_box,
                        "text": d["text"],
                        "score": d["score"]
                    })
                all_ocr_texts.extend(crop_texts)

                crop_cands = extract_iso_candidates(crop_texts)
                if crop_cands:
                    selected_crop_box = [cx1, cy1, cx2, cy2]
                    candidates.extend(crop_cands)

        # Fallback or complementary: if no valid candidate found from crops, run full-image OCR
        has_valid_candidate = any(validate_container_number(c["code"])[0] for c in candidates)
        if not has_valid_candidate:
            full_texts, full_dets = self.ocr.extract_texts_multipass(image)
            all_ocr_texts.extend(full_texts)
            all_ocr_detections.extend(full_dets)
            full_cands = extract_iso_candidates(full_texts)
            candidates.extend(full_cands)

        # Remove duplicate candidates preserving order
        unique_cands = []
        seen_codes = set()
        for c in candidates:
            if c["code"] not in seen_codes:
                seen_codes.add(c["code"])
                unique_cands.append(c)

        # Sort candidates: valid check digit first, then confidence
        def cand_sort_key(c):
            is_valid, _ = validate_container_number(c["code"])
            return (1 if is_valid else 0, c.get("confidence", 0))

        unique_cands.sort(key=cand_sort_key, reverse=True)

        # Best candidate
        best_cand = unique_cands[0] if unique_cands else None
        best_code = best_cand["code"] if best_cand else ""

        # Parse full structured metadata
        metadata = parse_container_info(best_code, all_ocr_texts) if best_code else {
            "container_number": "Not Found",
            "formatted_number": "Not Found",
            "owner_code": "",
            "owner_name": "",
            "category_char": "",
            "category_description": "",
            "serial_number": "",
            "check_digit": "",
            "expected_check_digit": "",
            "is_valid": False,
            "size_type_code": None,
            "size_type_desc": None
        }

        metadata["repaired"] = best_cand.get("repaired", False) if best_cand else False
        metadata["all_candidates"] = unique_cands
        metadata["detected_regions"] = detected_regions
        metadata["selected_crop_box"] = selected_crop_box
        metadata["raw_ocr_texts"] = all_ocr_texts
        metadata["ocr_detections"] = all_ocr_detections
        metadata["elapsed_time_ms"] = round((time.time() - t0) * 1000, 1)

        # Visualized annotated image
        annotated_bgr = self.annotate_image(image, metadata)
        annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
        metadata["annotated_image"] = annotated_rgb

        return metadata

    def annotate_image(self, image: np.ndarray, metadata: Dict) -> np.ndarray:
        """
        Draws visual annotations, bounding boxes, text overlays, and container badges.
        """
        vis = image.copy()
        h, w = vis.shape[:2]

        # 1. Draw detected container region boxes (Cyan/Blue)
        for r in metadata.get("detected_regions", []):
            x1, y1, x2, y2 = r["box"]
            conf = r["confidence"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 180, 0), 2)
            label = f"Region: {conf:.2f}"
            cv2.putText(vis, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 180, 0), 2)

        # 2. Draw OCR word polygons (Yellow/Green)
        for d in metadata.get("ocr_detections", []):
            box = np.array(d["box"], dtype=np.int32)
            cv2.polylines(vis, [box], isClosed=True, color=(0, 230, 255), thickness=1)

        # 3. Draw Top Information HUD Bar
        header_h = 75
        hud = np.zeros((header_h, w, 3), dtype=np.uint8)
        hud[:] = (26, 28, 35)  # Dark slate background

        # Code & Status
        code = metadata.get("container_number", "NOT FOUND")
        is_val = metadata.get("is_valid", False)
        repaired = metadata.get("repaired", False)

        if is_val:
            badge_color = (60, 190, 80) if not repaired else (0, 165, 255)
            badge_text = "ISO 6346 VALID" if not repaired else "AUTO-CORRECTED"
        elif code != "Not Found" and len(code) >= 10:
            badge_color = (50, 50, 220)
            badge_text = "CHECK DIGIT MISMATCH"
        else:
            badge_color = (120, 120, 120)
            badge_text = "NO CODE DETECTED"

        # Text on HUD
        formatted = metadata.get("formatted_number", code)
        cv2.putText(hud, f"CONTAINER: {formatted}", (15, 30), cv2.FONT_HERSHEY_DUPLEX, 0.75, (255, 255, 255), 2)
        
        # Badge
        cv2.rectangle(hud, (15, 42), (15 + len(badge_text) * 11 + 10, 68), badge_color, -1)
        cv2.putText(hud, badge_text, (20, 61), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # Operator & Size/Type on right side
        owner = metadata.get("owner_name", "")
        size_code = metadata.get("size_type_code", "")
        info_str = f"Owner: {owner[:28]}" if owner else ""
        if size_code:
            info_str += f" | Type: {size_code}"
        
        if info_str:
            cv2.putText(hud, info_str, (w - 380, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 220, 240), 1, cv2.LINE_AA)
        
        time_str = f"{metadata.get('elapsed_time_ms', 0)} ms"
        cv2.putText(hud, time_str, (w - 120, 61), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (160, 160, 160), 1, cv2.LINE_AA)

        # Composite HUD with image
        combined = np.vstack([hud, vis])
        return combined

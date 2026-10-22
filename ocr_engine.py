"""
OCR Engine module using RapidOCR (ONNX Runtime) with multi-pass container preprocessing.
"""
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from rapidocr_onnxruntime import RapidOCR


class ContainerOCREngine:
    def __init__(self):
        # Initialize RapidOCR engine
        self.engine = RapidOCR()

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhances image contrast using CLAHE on the luminance channel.
        Works well for shadows and faded paint on container corrugated steel.
        """
        if len(image.shape) == 2:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            return clahe.apply(image)

        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

    def upscale_if_small(self, image: np.ndarray, min_height: int = 150) -> np.ndarray:
        """
        Upscales small crops to improve character edge clarity for OCR.
        """
        h, w = image.shape[:2]
        if h < min_height and h > 0:
            scale = min_height / float(h)
            new_w = int(w * scale)
            return cv2.resize(image, (new_w, min_height), interpolation=cv2.INTER_CUBIC)
        return image

    def run_ocr(self, image: np.ndarray) -> List[Dict]:
        """
        Runs RapidOCR on an image array and returns parsed results:
        list of {'box': [[x1, y1], [x2, y2], [x3, y3], [x4, y4]], 'text': str, 'score': float}
        """
        if image is None or image.size == 0:
            return []

        try:
            results, elapse = self.engine(image)
        except Exception as e:
            return []

        if not results:
            return []

        parsed = []
        for item in results:
            # item format: [box, text, score_str]
            box = item[0]
            text = str(item[1]).strip()
            score = float(item[2]) if len(item) > 2 else 0.0
            parsed.append({
                "box": box,
                "text": text,
                "score": score
            })
        return parsed

    def extract_texts_multipass(self, image: np.ndarray) -> Tuple[List[str], List[Dict]]:
        """
        Multi-pass OCR extraction:
        1. Pass 1: Raw image
        2. Pass 2: Upscaled + CLAHE contrast enhancement
        3. Pass 3: Grayscale inverted
        Returns (list_of_text_strings, list_of_raw_detections)
        """
        all_texts = []
        all_detections = []
        seen_texts = set()

        # Pass 1: Raw
        p1 = self.run_ocr(image)
        for d in p1:
            t = d["text"]
            if t and t not in seen_texts:
                seen_texts.add(t)
                all_texts.append(t)
                all_detections.append(d)

        # Pass 2: Upscaled + CLAHE
        enhanced = self.enhance_contrast(self.upscale_if_small(image))
        p2 = self.run_ocr(enhanced)
        for d in p2:
            t = d["text"]
            if t and t not in seen_texts:
                seen_texts.add(t)
                all_texts.append(t)
                all_detections.append(d)

        return all_texts, all_detections

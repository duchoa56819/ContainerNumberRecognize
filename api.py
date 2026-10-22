"""
FastAPI REST API Server for Container Number Recognition and ISO 6346 Validation.
"""
import io
import os
import glob
import random
from typing import Optional
import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from pipeline import ContainerRecognitionPipeline
from container_parser import (
    validate_container_number,
    calculate_check_digit,
    get_step_by_step_calculation,
    parse_container_info
)

app = FastAPI(
    title="ContainerLens API",
    description="High-performance ISO 6346 Shipping Container Number Recognition & Validation API",
    version="1.0.0"
)

# Enable CORS for web/mobile client integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize pipeline
pipeline = ContainerRecognitionPipeline("weights/container_detector.pt")


class ValidateRequest(BaseModel):
    code: str


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ContainerLens API",
        "yolo_loaded": pipeline.yolo is not None,
        "ocr_engine": "RapidOCR (ONNX Runtime)"
    }


@app.post("/api/v1/predict")
async def predict_container(
    file: UploadFile = File(...),
    confidence: float = Form(0.20),
    use_detector: bool = Form(True),
    padding: float = Form(0.08)
):
    """
    Recognize container number from uploaded image.
    """
    try:
        contents = await file.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        res = pipeline.process(
            pil_image,
            conf_threshold=confidence,
            use_detector=use_detector,
            crop_padding=padding
        )

        # Exclude heavy numpy array from JSON response
        output = {k: v for k, v in res.items() if k != "annotated_image"}
        return output
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/validate")
def validate_code(req: ValidateRequest):
    """
    Validate container number against ISO 6346 standard and return owner details.
    """
    code = req.code.strip().upper()
    if len(code) < 10 or len(code) > 11:
        raise HTTPException(status_code=400, detail="Container number must be 10 or 11 characters.")

    info = parse_container_info(code)
    steps = get_step_by_step_calculation(code[:10])
    return {
        "validation_result": info,
        "modulo_11_steps": steps
    }


@app.get("/api/v1/sample")
def get_sample():
    """
    Returns random sample image path from the test dataset.
    """
    samples = glob.glob("test/images/*.jpg")
    if not samples:
        raise HTTPException(status_code=404, detail="No test images found.")
    chosen = random.choice(samples)
    return {"sample_file": os.path.basename(chosen), "path": chosen}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

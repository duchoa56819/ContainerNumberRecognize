"""
High-Performance Streaming Server with WebSockets for Android Camera Input.
"""
import io
import os
import socket
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn

from streaming_engine import StreamingRecognitionEngine

app = FastAPI(
    title="ContainerLens Android Streaming Backend",
    description="Low-latency WebSocket & Binary Streaming Server optimized for Android CameraX input.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent streaming engine
engine = StreamingRecognitionEngine("weights/container_detector.pt")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.get("/")
def index():
    ip = get_local_ip()
    return {
        "service": "ContainerLens Android Streaming Backend",
        "status": "ready",
        "websocket_endpoint": f"ws://{ip}:8000/api/v1/stream",
        "http_frame_endpoint": f"http://{ip}:8000/api/v1/stream/frame",
        "lan_ip": ip
    }


@app.get("/api/v1/stream/info")
def stream_info():
    ip = get_local_ip()
    return {
        "status": "online",
        "lan_ip": ip,
        "ws_url": f"ws://{ip}:8000/api/v1/stream",
        "model_loaded": engine.pipeline.yolo is not None
    }


@app.websocket("/api/v1/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    """
    Persistent WebSocket for live Android camera frame streaming.
    Receives binary JPEG bytes and returns structured JSON immediately.
    """
    await websocket.accept()
    print("Android client connected to WebSocket stream!")
    try:
        while True:
            # Receive binary frame from Android
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                frame_bytes = message["bytes"]
                # Process frame
                result = engine.process_frame_bytes(frame_bytes)
                # Send JSON response
                await websocket.send_text(json.dumps(result))
            elif "text" in message:
                # Can receive control commands (e.g., config changes)
                cmd = json.loads(message["text"])
                if cmd.get("action") == "ping":
                    await websocket.send_text(json.dumps({"status": "pong"}))
    except WebSocketDisconnect:
        print("Android client disconnected from stream.")
    except Exception as e:
        print(f"WebSocket error: {e}")


@app.post("/api/v1/stream/frame")
async def post_frame_binary(request: Request):
    """
    Ultra-low latency HTTP binary frame upload (avoids multipart overhead).
    Send raw image/jpeg in request body.
    """
    body = await request.body()
    if not body:
        return JSONResponse({"status": "error", "message": "Empty body"}, status_code=400)
    result = engine.process_frame_bytes(body)
    return JSONResponse(result)


if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 70)
    print("🚢 ContainerLens: Android Streaming Backend Server")
    print(f"📱 WebSocket Stream URL (LAN Wi-Fi) : ws://{local_ip}:8000/api/v1/stream")
    print(f"🔌 WebSocket Stream URL (USB / Local): ws://10.0.2.2:8000/api/v1/stream (Emulator)")
    print(f"                                      ws://localhost:8000/api/v1/stream (USB Reverse)")
    print(f"🚀 HTTP Binary Frame Endpoint       : http://{local_ip}:8000/api/v1/stream/frame")
    print("=" * 70)
    uvicorn.run("streaming_server:app", host="0.0.0.0", port=8000, reload=False)

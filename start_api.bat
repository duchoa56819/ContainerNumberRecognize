@echo off
echo ========================================================
echo Starting ContainerLens REST API Server (port 8000)
echo ========================================================
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
pause

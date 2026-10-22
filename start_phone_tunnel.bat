@echo off
echo ======================================================================
echo    ContainerLens - Global HTTPS Cloudflare Tunnel for Phone Camera
echo ======================================================================
echo.
echo Starting secure public HTTPS tunnel to port 8000...
echo.
echo Once started, look for the 'https://*.trycloudflare.com' URL below.
echo Open that HTTPS URL on your phone's browser to access the camera with SSL!
echo.
if exist "..\Identify\cloudflared.exe" (
    ..\Identify\cloudflared.exe tunnel --url http://127.0.0.1:8000
) else if exist "cloudflared.exe" (
    cloudflared.exe tunnel --url http://127.0.0.1:8000
) else (
    echo Error: cloudflared.exe not found.
)
pause

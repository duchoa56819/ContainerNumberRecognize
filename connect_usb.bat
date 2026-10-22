@echo off
echo ======================================================================
echo    ContainerLens - Android USB Reverse Port Forwarding
echo ======================================================================
echo.
echo Setting up reverse port forwarding (Phone port 8000 -> PC port 8000)...
adb reverse tcp:8000 tcp:8000
adb reverse tcp:8501 tcp:8501
echo.
echo Active reverse tunnels:
adb reverse --list
echo.
echo ======================================================================
echo Done! On your phone's Chrome browser, open:
echo    http://localhost:8000/camera
echo ======================================================================
pause

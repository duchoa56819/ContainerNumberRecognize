@echo off
echo ======================================================================
echo    ContainerLens - Install Native Android App to Device
echo ======================================================================
echo.
echo Checking for connected Android devices via ADB...
adb devices
echo.
echo Installing ContainerLens Android APK...
adb install -r android-app\app\build\outputs\apk\debug\app-debug.apk
echo.
echo Setting up reverse port forward for USB connection (Phone -> PC port 8000)...
adb reverse tcp:8000 tcp:8000
echo.
echo ======================================================================
echo Installation complete! 
echo Open 'ContainerLens' on your Android phone.
echo ======================================================================
pause

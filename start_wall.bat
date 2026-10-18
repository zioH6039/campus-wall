@echo off
rem ==== 校园闲置信息墙 · 后台启动（不弹窗口） ====
cd /d "%~dp0"

set "PYW=C:\Users\16504\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe"
if not exist "%PYW%" (
  echo [ERROR] pythonw not found: %PYW%
  pause
  exit /b 1
)

start "" "%PYW%" "%~dp0run_service.py"
echo.
echo Service starting in background.
echo Public URL will appear in:  %~dp0public_url.txt
echo Logs:  %~dp0logs\
echo.
timeout /t 3 >nul

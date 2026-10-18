@echo off
rem ==== 校园闲置信息墙 · 停止后台服务 ====
cd /d "%~dp0"
set "PY=C:\Users\16504\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0stop_service.py"
timeout /t 2 >nul

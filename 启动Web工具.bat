@echo off
REM 共享CFO - Web工具启动脚本

cd /d "%~dp0"

echo ========================================
echo   共享CFO - Web查询监控工具
echo ========================================
echo.
echo 正在启动Web服务器...
echo.

python web_tool.py

pause

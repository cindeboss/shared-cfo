@echo off
REM 共享CFO - 本地工具启动脚本

setlocal enabledelayedexpansion

echo ========================================
echo   共享CFO - 数据查询 & 监控工具
echo ========================================
echo.

:menu
echo 请选择功能:
echo.
echo [1] 查看数据统计
echo [2] 搜索政策文件
echo [3] 列出最近政策
echo [4] 查看政策详情
echo [5] 导出数据
echo [6] 监控爬虫状态
echo [7] 实时监控模式
echo [8] 检查爬虫服务
echo [0] 退出
echo.

set /p choice=请输入选项:

if "%choice%"=="1" goto stats
if "%choice%"=="2" goto search
if "%choice%"=="3" goto list
if "%choice%"=="4" goto view
if "%choice%"=="5" goto export
if "%choice%"=="6" goto monitor
if "%choice%"=="7" goto watch
if "%choice%"=="8" goto status
if "%choice%"=="0" goto end
goto menu

:stats
python policy_query.py stats
pause
goto menu

:search
set /p keyword=请输入搜索关键词:
python policy_query.py search "%keyword%" --interactive
pause
goto menu

:list
python policy_query.py list
pause
goto menu

:view
set /p policy_id=请输入 Policy ID:
python policy_query.py view "%policy_id%"
pause
goto menu

:export
set /p keyword=请输入搜索关键词 (可选):
python policy_query.py export "%keyword%" -o export.md
pause
goto menu

:monitor
python crawler_monitor.py monitor --hours 24
pause
goto menu

:watch
python crawler_monitor.py watch
pause
goto menu

:status
python crawler_monitor.py status
pause
goto menu

:end
echo 感谢使用！
timeout /t 2 >nul
exit /b 0

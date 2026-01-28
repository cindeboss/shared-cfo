@echo off
echo =====================================
echo   共享CFO爬虫 - 一键部署脚本
echo   请确保您已通过阿里云控制台连接到服务器
echo =====================================
echo.
echo 正在准备远程执行命令...

set SERVER=120.78.5.4
set USER=root
set PASS=840307@whY

echo 正在测试服务器连接...
ping %SERVER% -n 2 >nul

echo.
echo =====================================
echo   准备就绪！
echo =====================================
echo.
echo 请按以下步骤操作：
echo.
echo 1. 打开阿里云控制台：https://ecs.console.aliyun.com/
echo 2. 找到ECS实例 (120.78.5.4)
echo 3. 点击"远程连接" → 选择"VNC连接"或"Workbench"
echo 4. 连接成功后，复制以下命令：
echo.
echo =====================================
echo.
echo   cd /opt/shared_cfc && source venv/bin/activate && python crawler.py
echo.
echo =====================================
echo.
pause

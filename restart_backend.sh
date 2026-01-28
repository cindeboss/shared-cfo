#!/bin/bash
cd /opt/shared_cfo

# 停止旧进程
pkill -f 'uvicorn app.main' 2>/dev/null
pkill -f 'backend.app.main' 2>/dev/null
sleep 2

# 启动后端
python3 -m backend.app.main --host 0.0.0.0 --port 8001 > logs/backend.log 2>&1 &

sleep 3

# 测试
echo "Testing API..."
curl -s http://localhost:8001/health
echo ""
curl -s http://localhost:8001/api/v1/crawler/stats
echo ""
echo "Done!"

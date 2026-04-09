#!/bin/bash
set -e
WORKSPACE="/vol1/@apphome/trim.openclaw/data/workspace/exam-system"
cd "$WORKSPACE"

echo "[Deploy] 备份数据库..."
cp exam.db "exam.db.bak_$(date +%Y%m%d_%H%M%S)"

echo "[Deploy] 安装依赖..."
pip3 install flask requests APScheduler --break-system-packages -q 2>&1 | tail -1

echo "[Deploy] 重启服务..."
pkill -f "python3 app.py" || true
sleep 2
nohup python3 app.py >> app.log 2>&1 &
PID=$!
echo "[Deploy] PID: $PID"
sleep 3

echo "[Deploy] 验证服务..."
curl -s http://127.0.0.1:7758/ | head -c 200
echo ""
echo "[Deploy] 完成！"
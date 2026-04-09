#!/bin/bash
# 云计算考试系统启动脚本
cd "$(dirname "$0")"

echo "=========================================="
echo "  ☁️  云计算考试系统"
echo "=========================================="

# 检查依赖
if ! python3 -c "import flask" 2>/dev/null; then
    echo "[ERROR] Flask 未安装，请先运行: pip install flask"
    exit 1
fi

# 初始化数据库（包含示例题目）
echo "[*] 初始化数据库..."
python3 init_db.py

# 启动服务
echo "[*] 启动 Flask 服务..."
echo "[*] 访问地址: http://localhost:7758"
PORT=7758 python3 app.py

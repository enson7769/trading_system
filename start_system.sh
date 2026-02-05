#!/bin/bash

# 启动脚本：同时启动交易系统和仪表盘

echo "=== 启动交易系统和仪表盘 ==="
echo "1. 启动交易系统..."
echo "2. 启动仪表盘..."
echo ""
echo "交易系统将在这个终端运行"
echo "仪表盘将在浏览器中打开: http://localhost:8501"
echo ""
echo "按 Ctrl+C 停止整个系统"
echo ""

# 启动交易系统
python main.py --no-dashboard &
TRADING_SYSTEM_PID=$!

# 等待交易系统初始化
echo "等待交易系统初始化..."
sleep 5

# 启动仪表盘
echo "启动仪表盘..."
python -m streamlit run dashboard/monitoring.py --server.headless true --server.port 8501 --server.address localhost &
DASHBOARD_PID=$!

# 等待仪表盘启动
echo "等待仪表盘启动..."
sleep 5

# 显示状态
echo ""
echo "系统启动完成!"
echo "仪表盘: http://localhost:8501"
echo ""
echo "按 Ctrl+C 停止整个系统"
echo ""

# 等待用户输入
wait $TRADING_SYSTEM_PID $DASHBOARD_PID

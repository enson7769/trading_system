# 启动脚本：同时启动交易系统和仪表盘

Write-Host "=== 启动交易系统和仪表盘 ==="
Write-Host "1. 启动交易系统..."
Write-Host "2. 启动仪表盘..."
Write-Host ""
Write-Host "交易系统将在这个终端运行"
Write-Host "仪表盘将在浏览器中打开: http://localhost:8501"
Write-Host ""
Write-Host "按 Ctrl+C 停止整个系统"
Write-Host ""

# 启动仪表盘在后台
Write-Host "启动仪表盘..."
Start-Process -FilePath "python" -ArgumentList "-m", "streamlit", "run", "dashboard/monitoring.py", "--server.headless", "true", "--server.port", "8501", "--server.address", "localhost"

# 等待仪表盘启动
Write-Host "等待仪表盘启动..."
Start-Sleep -Seconds 5

# 启动交易系统（在前台运行）
Write-Host "启动交易系统..."
python main.py --no-dashboard

import sys
import os
import threading
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
from decimal import Decimal
from core.models import Instrument
from account.account_manager import AccountManager
from gateways.polymarket_gateway import PolymarketGateway
from gateways.binance_gateway import BinanceGateway
from engine.execution_engine import ExecutionEngine
from security.credential_manager import CredentialManager
from dashboard.data_service import data_service
from config.config import config
from utils.logger import logger

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-input", action="store_true", help="仅使用环境变量")
    parser.add_argument("--no-dashboard", action="store_true", help="跳过启动监控仪表盘")
    args = parser.parse_args()

    cred_mgr = CredentialManager()
    acc_mgr = AccountManager()
    
    # 从配置加载账户配置
    # 主账户 (Polymarket)
    account_config = config.get_account_config('main_account')
    acc_mgr.add_account(
        "main_account", 
        account_config.get('gateway', 'polymarket'), 
        account_config.get('initial_balances', {"USDC": 10000})
    )
    
    # 币安账户
    binance_account_config = config.get_account_config('binance_account')
    acc_mgr.add_account(
        "binance_account", 
        binance_account_config.get('gateway', 'binance'), 
        binance_account_config.get('initial_balances', {"USDC": 10000, "BTC": 1.0, "ETH": 10.0})
    )

    # 从配置加载网关配置
    # Polymarket网关
    gateway_config = config.get_gateway_config('polymarket')
    poly_gw = PolymarketGateway(
        gateway_config.get('rpc_url', 'https://polygon-rpc.com/'), 
        cred_mgr, 
        mock=gateway_config.get('mock', False)
    )
    poly_gw.no_input = args.no_input
    poly_gw.connect()
    
    # 币安网关
    binance_config = config.get_gateway_config('binance')
    binance_gw = BinanceGateway(
        cred_mgr, 
        mock=binance_config.get('mock', False)
    )
    binance_gw.no_input = args.no_input
    binance_gw.connect()

    engine = ExecutionEngine(acc_mgr, {"polymarket": poly_gw, "binance": binance_gw})
    
    # 初始化仪表盘数据服务
    data_service.initialize(engine)
    logger.info("仪表盘数据服务初始化完成")
    
    # 如果未禁用，在单独线程中启动仪表盘
    if not args.no_dashboard:
        logger.info("正在启动监控仪表盘...")
        print("\n=== 启动监控仪表盘 ===")
        dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
        dashboard_thread.start()
        # 给仪表盘启动时间
        print("给仪表盘启动时间...")
        time.sleep(5)  # 增加睡眠时间以确保仪表盘有足够时间启动

    logger.info("\n=== 交易系统启动完成 ===")
    logger.info("系统已准备好进行交易操作")
    logger.info("请查看仪表盘进行监控和控制")
    
    # 打印启动消息到控制台
    print("\n交易系统启动成功！")
    print("仪表盘地址: http://localhost:8501")
    print("\n系统已准备好进行交易操作。")
    print("使用仪表盘监控和控制系统。")

# 启动Streamlit仪表盘函数
def start_dashboard():
    """在单独线程中启动Streamlit仪表盘"""
    import subprocess
    import sys
    import time
    
    try:
        # 启动Streamlit仪表盘
        streamlit_cmd = [
            sys.executable,
            "-m", "streamlit",
            "run", "dashboard/monitoring.py",
            "--server.headless", "true",
            "--server.port", "8501",
            "--server.address", "localhost"
        ]
        
        logger.info(f"正在启动仪表盘，命令: {' '.join(streamlit_cmd)}")
        print(f"\n正在启动仪表盘，命令: {' '.join(streamlit_cmd)}")
        
        # 在后台运行Streamlit
        process = subprocess.Popen(
            streamlit_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # 监控进程输出
        start_time = time.time()
        success = False
        while time.time() - start_time < 30:  # 30秒后超时
            line = process.stdout.readline()
            if not line:
                break
            
            print(f"[仪表盘] {line.strip()}")
            
            if "You can now view your Streamlit app in your browser" in line:
                logger.info("仪表盘启动成功！")
                print("\n仪表盘启动成功！")
                print("仪表盘地址: http://localhost:8501")
                success = True
                break
            elif "Error" in line or "Exception" in line:
                logger.error(f"仪表盘错误: {line.strip()}")
                print(f"\n仪表盘错误: {line.strip()}")
        
        if not success:
            if time.time() - start_time >= 30:
                logger.error("仪表盘启动超时，超过30秒")
                print("\n仪表盘启动超时，超过30秒")
            else:
                logger.error("仪表盘启动失败，原因未知")
                print("\n仪表盘启动失败，原因未知")
        
        # 保持进程在后台运行
        def monitor_process():
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                if "Error" in line or "Exception" in line:
                    logger.error(f"仪表盘错误: {line.strip()}")
        
        import threading
        monitor_thread = threading.Thread(target=monitor_process, daemon=True)
        monitor_thread.start()
            
    except Exception as e:
        logger.error(f"启动仪表盘失败: {e}")
        print(f"\n启动仪表盘失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
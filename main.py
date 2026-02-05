import sys
import os
import threading
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
from account.account_manager import AccountManager
from gateways.polymarket_gateway import PolymarketGateway
from engine.execution_engine import ExecutionEngine
from security.credential_manager import CredentialManager
from dashboard.data_service import data_service
from config.config import config
from utils.logger import logger
from strategy.polymarket_strategy import PolymarketStrategy
from strategy.strategy_executor import StrategyExecutor

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
    


    engine = ExecutionEngine(acc_mgr, {"polymarket": poly_gw})
    
    # 初始化Polymarket策略
    poly_strategy = PolymarketStrategy(poly_gw)
    logger.info("Polymarket策略初始化完成")
    
    # 初始化策略执行器
    strategy_executor = StrategyExecutor(engine, poly_strategy, poly_gw)
    
    # 添加一些默认的监控市场
    # 这里可以从配置文件加载，或者通过API获取热门市场
    default_markets = []
    try:
        # 尝试获取一些事件和市场
        events = poly_gw.get_events()
        if events:
            for event in events[:3]:  # 只获取前3个事件
                markets = event.get('markets', [])
                for market in markets[:2]:  # 每个事件只获取前2个市场
                    market_id = market.get('id')
                    if market_id:
                        default_markets.append(market_id)
        
        if default_markets:
            strategy_executor.set_markets(default_markets)
            logger.info(f"已添加默认监控市场: {default_markets}")
        else:
            logger.warning("未添加默认监控市场，监控列表为空")
    except Exception as e:
        logger.error(f"获取默认市场失败: {e}")
    
    # 启动策略执行器
    strategy_executor.start()
    logger.info("策略执行器启动完成")
    
    # 初始化仪表盘数据服务
    data_service.initialize(engine)
    logger.info("仪表盘数据服务初始化完成")
    
    # 启动事件监听器（模拟）
    event_listener_thread = threading.Thread(target=event_listener, args=(strategy_executor,), daemon=True)
    event_listener_thread.start()
    logger.info("事件监听器已启动")
    
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

def event_listener(strategy_executor):
    """事件监听器（模拟）
    
    模拟外部事件的触发，用于测试事件触发的自动下单功能
    
    Args:
        strategy_executor: 策略执行器实例
    """
    import time
    import random
    
    # 模拟事件列表
    mock_events = [
        'powell_speech',
        'unemployment_rate',
        'cpi',
        'ppi',
        'fomc_meeting',
        'gdp',
        'retail_sales',
        'nonfarm_payrolls'
    ]
    
    # 模拟事件数据
    mock_event_data = {
        'powell_speech': {
            'title': 'Fed Chair Powell Speech',
            'content': 'Powell discusses monetary policy and economic outlook',
            'impact': 'high'
        },
        'unemployment_rate': {
            'rate': 3.8,
            'previous': 3.9,
            'change': -0.1,
            'impact': 'medium'
        },
        'cpi': {
            'rate': 2.1,
            'previous': 2.2,
            'change': -0.1,
            'impact': 'high'
        },
        'ppi': {
            'rate': 1.9,
            'previous': 2.0,
            'change': -0.1,
            'impact': 'medium'
        },
        'fomc_meeting': {
            'decision': 'hold',
            'rate': 5.25,
            'statement': 'FOMC decides to hold interest rates steady',
            'impact': 'high'
        },
        'gdp': {
            'growth_rate': 2.4,
            'previous': 2.0,
            'change': 0.4,
            'impact': 'high'
        },
        'retail_sales': {
            'growth_rate': 0.5,
            'previous': 0.3,
            'change': 0.2,
            'impact': 'medium'
        },
        'nonfarm_payrolls': {
            'jobs_added': 187000,
            'unemployment_rate': 3.8,
            'wage_growth': 0.2,
            'impact': 'high'
        }
    }
    
    logger.info("事件监听器已启动，开始模拟外部事件")
    
    # 模拟事件触发
    while True:
        try:
            # 随机选择一个事件
            event_name = random.choice(mock_events)
            event_data = mock_event_data.get(event_name, {})
            
            # 模拟事件触发
            logger.info(f"模拟事件触发: {event_name}")
            print(f"\n[事件监听器] 模拟事件触发: {event_name}")
            
            # 调用策略执行器的事件处理方法
            result = strategy_executor.handle_event(event_name, event_data)
            
            # 打印事件处理结果
            logger.info(f"事件处理结果: {result}")
            print(f"[事件监听器] 事件处理结果: {result.get('status')}")
            if 'order_status' in result:
                print(f"[事件监听器] 订单状态: {result.get('order_status')}")
                print(f"[事件监听器] 订单数量: {result.get('order_count', 0)}")
            
            # 随机等待一段时间，模拟事件的随机性
            wait_time = random.randint(30, 120)  # 30-120秒
            logger.info(f"事件监听器将等待 {wait_time} 秒后触发下一个事件")
            time.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"事件监听器错误: {e}")
            import traceback
            traceback.print_exc()
            # 等待一段时间后继续
            time.sleep(30)

if __name__ == "__main__":
    main()
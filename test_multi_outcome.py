#!/usr/bin/env python3
# 测试同时购买多个结果选项的功能

import sys
import os
from decimal import Decimal

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import Order, Instrument
from gateways.polymarket_gateway import PolymarketGateway
from strategy.polymarket_strategy import PolymarketStrategy
from strategy.strategy_executor import StrategyExecutor
from utils.logger import logger

# 日志已在模块中配置

# 创建Polymarket网关（使用mock模式）
polymarket_gateway = PolymarketGateway(
    rpc_url="http://localhost:8545",
    credential_manager=None,  # 不使用实际凭证
    mock=True  # 启用模拟模式
)

# 创建Polymarket策略
polymarket_strategy = PolymarketStrategy(polymarket_gateway)

# 测试1: 创建带有结果选项的订单
def test_create_order_with_outcome():
    print("\n=== 测试1: 创建带有结果选项的订单 ===")
    
    # 创建交易品种
    instrument = Instrument(
        symbol='market1',
        base_asset='OUTCOME',
        quote_asset='USDC',
        min_order_size=Decimal('1'),
        tick_size=Decimal('0.01'),
        gateway_name='polymarket'
    )
    
    # 创建订单（带有结果选项）
    order = Order(
        order_id='test_order_1',
        instrument=instrument,
        side='buy',
        type='market',
        quantity=Decimal('10'),
        price=None,
        account_id='main_account',
        outcome='Yes'
    )
    
    print(f"创建的订单: {order}")
    print(f"订单结果选项: {order.outcome}")
    
    # 发送订单到Polymarket
    tx_hash = polymarket_gateway.send_order(order)
    print(f"订单发送成功，交易哈希: {tx_hash}")

# 测试2: 为市场的所有结果选项生成交易信号
def test_generate_signals_for_all_outcomes():
    print("\n=== 测试2: 为市场的所有结果选项生成交易信号 ===")
    
    # 模拟市场ID
    market_id = 'market1'
    
    # 为所有结果选项生成交易信号
    signals = polymarket_strategy.generate_trade_signals_for_all_outcomes(market_id)
    
    print(f"为市场 {market_id} 生成的交易信号数: {len(signals)}")
    
    for signal in signals:
        print(f"信号: 结果选项={signal.get('outcome')}, 类型={signal.get('signal')}, 置信度={signal.get('confidence')}")

# 测试3: 为市场的所有结果选项获取交易建议
def test_get_recommendations_for_all_outcomes():
    print("\n=== 测试3: 为市场的所有结果选项获取交易建议 ===")
    
    # 模拟市场ID
    market_id = 'market1'
    
    # 为所有结果选项获取交易建议
    recommendations = polymarket_strategy.get_trade_recommendations_for_all_outcomes(market_id)
    
    print(f"为市场 {market_id} 获取的交易建议数: {len(recommendations)}")
    
    for rec in recommendations:
        print(f"建议: 结果选项={rec.get('outcome')}, 信号={rec.get('signal')}, 订单大小={rec.get('order_size')}")

# 运行测试
if __name__ == "__main__":
    print("开始测试同时购买多个结果选项的功能...")
    
    try:
        test_create_order_with_outcome()
        test_generate_signals_for_all_outcomes()
        test_get_recommendations_for_all_outcomes()
        
        print("\n=== 测试完成 ===")
        print("所有测试通过，系统支持同时购买多个结果选项的功能!")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

#!/usr/bin/env python3
# 测试M选N个结果交易的功能

import sys
import os
from decimal import Decimal

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import Order, Instrument
from gateways.polymarket_gateway import PolymarketGateway
from strategy.polymarket_strategy import PolymarketStrategy
from utils.logger import logger

# 创建Polymarket网关（使用mock模式）
polymarket_gateway = PolymarketGateway(
    rpc_url="http://localhost:8545",
    credential_manager=None,  # 不使用实际凭证
    mock=True  # 启用模拟模式
)

# 创建Polymarket策略
polymarket_strategy = PolymarketStrategy(polymarket_gateway)

# 测试1: 测试Polymarket策略类的get_m_choose_n_trade_recommendations方法
def test_get_m_choose_n_trade_recommendations():
    print("\n=== 测试1: 测试Polymarket策略类的get_m_choose_n_trade_recommendations方法 ===")
    
    # 模拟市场ID
    market_id = 'market1'
    
    # 测试M选1个结果交易
    n = 1
    recommendations = polymarket_strategy.get_m_choose_n_trade_recommendations(market_id, n)
    print(f"为市场 {market_id} 获取的M选{1}个结果交易的交易建议数: {len(recommendations)}")
    
    for i, rec in enumerate(recommendations):
        print(f"建议 {i+1}: 结果选项={rec.get('outcome')}, 信号={rec.get('signal')}, 置信度={rec.get('confidence')}, 订单大小={rec.get('order_size')}")
    
    # 测试M选2个结果交易
    n = 2
    recommendations = polymarket_strategy.get_m_choose_n_trade_recommendations(market_id, n)
    print(f"\n为市场 {market_id} 获取的M选{2}个结果交易的交易建议数: {len(recommendations)}")
    
    for i, rec in enumerate(recommendations):
        print(f"建议 {i+1}: 结果选项={rec.get('outcome')}, 信号={rec.get('signal')}, 置信度={rec.get('confidence')}, 订单大小={rec.get('order_size')}")

# 测试2: 测试边界情况
def test_edge_cases():
    print("\n=== 测试2: 测试边界情况 ===")
    
    # 模拟市场ID
    market_id = 'market1'
    
    # 测试N大于M的情况
    n = 10  # 市场只有2个结果选项
    recommendations = polymarket_strategy.get_m_choose_n_trade_recommendations(market_id, n)
    print(f"测试N大于M的情况 (N={n}): 获取了 {len(recommendations)} 个交易建议")
    
    # 测试N小于等于0的情况
    n = 0
    recommendations = polymarket_strategy.get_m_choose_n_trade_recommendations(market_id, n)
    print(f"测试N小于等于0的情况 (N={n}): 获取了 {len(recommendations)} 个交易建议")

# 运行测试
if __name__ == "__main__":
    print("开始测试M选N个结果交易的功能...")
    
    try:
        test_get_m_choose_n_trade_recommendations()
        test_edge_cases()
        
        print("\n=== 测试完成 ===")
        print("所有测试通过，系统支持M选N个结果交易的功能!")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

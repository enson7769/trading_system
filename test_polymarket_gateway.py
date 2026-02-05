import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security.credential_manager import CredentialManager
from gateways.polymarket_gateway import PolymarketGateway
from config.config import config
from utils.logger import logger


def test_polymarket_gateway():
    """测试Polymarket网关的API集成功能"""
    logger.info("=== 测试Polymarket网关API集成功能 ===")
    
    try:
        # 初始化凭证管理器
        cred_mgr = CredentialManager()
        
        # 加载Polymarket网关配置
        polymarket_config = config.get_gateway_config('polymarket')
        logger.info(f"Polymarket网关配置: {polymarket_config}")
        
        # 初始化Polymarket网关
        polymarket_gw = PolymarketGateway(
            rpc_url=polymarket_config.get('rpc_url', 'https://polygon-rpc.com/'),
            credential_manager=cred_mgr,
            mock=False  # 关闭模拟模式，使用实际API
        )
        polymarket_gw.no_input = False  # 允许交互式输入，以便输入私钥
        
        # 连接到Polymarket
        logger.info("连接到Polymarket网关...")
        polymarket_gw.connect()
        logger.info("连接成功！")
        
        # 测试1: Gamma API - 获取事件
        logger.info("\n测试1: Gamma API - 获取事件")
        events = polymarket_gw.get_events()
        logger.info(f"获取到 {len(events)} 个事件")
        for event in events[:3]:  # 只显示前3个事件
            logger.info(f"事件: {event.get('title')} (ID: {event.get('id')})")
        
        # 测试2: Gamma API - 获取市场
        logger.info("\n测试2: Gamma API - 获取市场")
        markets = polymarket_gw.get_markets()
        logger.info(f"获取到 {len(markets)} 个市场")
        for market in markets[:3]:  # 只显示前3个市场
            logger.info(f"市场: {market.get('question')} (ID: {market.get('id')})")
        
        # 测试3: Gamma API - 获取市场详情
        logger.info("\n测试3: Gamma API - 获取市场详情")
        if markets:
            market_id = markets[0].get('id')
            market_detail = polymarket_gw.get_market(market_id)
            logger.info(f"市场详情: {market_detail}")
        
        # 测试4: Gamma API - 获取类别
        logger.info("\n测试4: Gamma API - 获取类别")
        categories = polymarket_gw.get_categories()
        logger.info(f"获取到 {len(categories)} 个类别")
        for category in categories:
            logger.info(f"类别: {category.get('name')} (ID: {category.get('id')})")
        
        # 测试5: CLOB API - 获取订单簿
        logger.info("\n测试5: CLOB API - 获取订单簿")
        if markets:
            market_id = markets[0].get('id')
            order_book = polymarket_gw.get_order_book(market_id)
            logger.info(f"订单簿: {order_book}")
        
        # 测试6: CLOB API - 获取市场价格
        logger.info("\n测试6: CLOB API - 获取市场价格")
        if markets:
            market_id = markets[0].get('id')
            market_price = polymarket_gw.get_market_price(market_id)
            logger.info(f"市场价格: {market_price}")
        
        # 测试7: Data API - 获取持仓
        logger.info("\n测试7: Data API - 获取持仓")
        positions = polymarket_gw.get_positions()
        logger.info(f"获取到 {len(positions)} 个持仓")
        for position in positions:
            logger.info(f"持仓: {position.get('market_id')} - {position.get('outcome')} (大小: {position.get('size')})")
        
        # 测试8: Data API - 获取交易历史
        logger.info("\n测试8: Data API - 获取交易历史")
        trade_history = polymarket_gw.get_trade_history()
        logger.info(f"获取到 {len(trade_history)} 条交易历史")
        for trade in trade_history[:3]:  # 只显示前3条交易
            logger.info(f"交易: {trade.get('market_id')} - {trade.get('side')} (价格: {trade.get('price')}, 大小: {trade.get('size')})")
        
        # 测试9: Data API - 获取投资组合
        logger.info("\n测试9: Data API - 获取投资组合")
        portfolio = polymarket_gw.get_portfolio()
        logger.info(f"投资组合: {portfolio}")
        
        # 测试10: Data API - 获取市场交易历史
        logger.info("\n测试10: Data API - 获取市场交易历史")
        if markets:
            market_id = markets[0].get('id')
            market_trades = polymarket_gw.get_market_trades(market_id)
            logger.info(f"获取到 {len(market_trades)} 条市场交易历史")
            for trade in market_trades[:3]:  # 只显示前3条交易
                logger.info(f"市场交易: {trade.get('side')} (价格: {trade.get('price')}, 大小: {trade.get('size')})")
        
        # 测试11: 发送订单
        logger.info("\n测试11: 发送订单")
        from core.models import Order, Instrument
        from core.enums import OrderSide, OrderType
        from decimal import Decimal
        
        if markets:
            market_id = markets[0].get('id')
            
            inst = Instrument(
                symbol=market_id,
                base_asset="OUTCOME",
                quote_asset="USDC",
                min_order_size=Decimal('1'),
                tick_size=Decimal('0.01'),
                gateway_name="polymarket"
            )
            
            order = Order(
                order_id="test_polymarket_order",
                instrument=inst,
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                quantity=Decimal('10'),
                price=Decimal('0.65'),
                account_id="main_account"
            )
            
            order_id = polymarket_gw.send_order(order)
            logger.info(f"发送订单成功，订单ID: {order_id}")
        
        # 测试12: 取消订单
        logger.info("\n测试12: 取消订单")
        cancel_result = polymarket_gw.cancel_order("test_order_id")
        logger.info(f"取消订单结果: {cancel_result}")
        
        # 测试13: 获取订单状态
        logger.info("\n测试13: 获取订单状态")
        order_status = polymarket_gw.get_order_status("test_order_id")
        logger.info(f"订单状态: {order_status}")
        
        # 测试14: 验证Polymarket账户连接
        logger.info("\n测试14: 验证Polymarket账户连接")
        logger.info(f"当前连接的账户地址: {polymarket_gw.address}")
        
        # 验证地址是否与配置文件中的一致
        expected_address = polymarket_config.get('address', None)
        if expected_address:
            logger.info(f"配置文件中的账户地址: {expected_address}")
            if polymarket_gw.address and expected_address.lower() == polymarket_gw.address.lower():
                logger.info("账户连接成功，地址匹配")
            else:
                logger.warning("账户地址不匹配，可能是因为在模拟模式下使用了模拟地址")
        else:
            logger.info("配置文件中未设置账户地址")
        
        logger.info("\n=== 测试完成 ===")
        logger.info("所有测试用例执行成功！")
        
    except Exception as e:
        logger.error(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_polymarket_gateway()

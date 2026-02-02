import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security.credential_manager import CredentialManager
from gateways.binance_gateway import BinanceGateway
from config.config import config
from utils.logger import logger

def test_binance_gateway():
    """测试币安网关的出入币功能"""
    logger.info("=== 测试币安网关出入币功能 ===")
    
    try:
        # 初始化凭证管理器
        cred_mgr = CredentialManager()
        
        # 加载币安网关配置
        binance_config = config.get_gateway_config('binance')
        logger.info(f"币安网关配置: {binance_config}")
        
        # 初始化币安网关
        binance_gw = BinanceGateway(
            cred_mgr, 
            mock=binance_config.get('mock', True)
        )
        binance_gw.no_input = True
        
        # 连接到币安
        logger.info("连接到币安网关...")
        binance_gw.connect()
        logger.info("连接成功！")
        
        # 测试1: 获取账户余额
        logger.info("\n测试1: 获取账户余额")
        balance = binance_gw.get_account_balance()
        logger.info(f"账户余额: {balance}")
        
        # 测试2: 获取特定币种余额
        logger.info("\n测试2: 获取特定币种余额")
        usdc_balance = binance_gw.get_account_balance('USDC')
        logger.info(f"USDC余额: {usdc_balance}")
        
        btc_balance = binance_gw.get_account_balance('BTC')
        logger.info(f"BTC余额: {btc_balance}")
        
        # 测试3: 获取充值历史
        logger.info("\n测试3: 获取充值历史")
        deposit_history = binance_gw.deposit_history('USDC')
        logger.info(f"USDC充值历史: {deposit_history}")
        
        # 测试4: 获取提现历史
        logger.info("\n测试4: 获取提现历史")
        withdraw_history = binance_gw.withdraw_history('USDC')
        logger.info(f"USDC提现历史: {withdraw_history}")
        
        # 测试5: 测试提现功能
        logger.info("\n测试5: 测试提现功能")
        withdraw_result = binance_gw.withdraw(
            coin='USDC',
            amount=100.0,
            address='0xWithdrawAddress12345678901234567890123456789012',
            network='BSC'
        )
        logger.info(f"提现结果: {withdraw_result}")
        
        # 测试6: 测试发送订单
        logger.info("\n测试6: 测试发送订单")
        from core.models import Order, Instrument
        from core.enums import OrderSide, OrderType
        from decimal import Decimal
        
        inst = Instrument(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            min_order_size=Decimal('0.001'),
            tick_size=Decimal('0.01'),
            gateway_name="binance"
        )
        
        order = Order(
            order_id="test_binance_order",
            instrument=inst,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            quantity=Decimal('0.001'),
            price=Decimal('40000'),
            account_id="binance_account"
        )
        
        order_id = binance_gw.send_order(order)
        logger.info(f"发送订单成功，订单ID: {order_id}")
        
        logger.info("\n=== 测试完成 ===")
        logger.info("所有测试用例执行成功！")
        
    except Exception as e:
        logger.error(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_binance_gateway()

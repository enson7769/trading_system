from decimal import Decimal
from datetime import datetime, timedelta
from core.models import AccountInfo, Order
from typing import Dict, List, Optional
import os
import json

class RiskManager:
    def __init__(self, config_file: str = "data/risk_config.json"):
        """初始化风险管理器
        
        Args:
            config_file: 风险配置文件路径
        """
        self.config_file = config_file
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        # 加载风险配置
        self.config = self._load_config()
        # 交易记录
        self.trade_history: List[Dict[str, Any]] = []
        # 市场暴露
        self.market_exposure: Dict[str, Decimal] = {}
        # 当日交易金额
        self.daily_trade_amount = Decimal('0')
        self.last_reset_date = datetime.now().date()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载风险配置"""
        default_config = {
            'max_order_size': 1000,  # 单笔订单最大规模（USDC）
            'daily_trade_limit': 10000,  # 日交易限额（USDC）
            'max_market_exposure': 5000,  # 单个市场最大暴露（USDC）
            'price_deviation_threshold': 0.05,  # 价格偏差阈值（5%）
            'max_trades_per_minute': 10,  # 每分钟最大交易次数
            'stop_loss_percent': 0.05,  # 止损百分比（5%）
            'max_position_size': 10000  # 最大持仓规模（USDC）
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载风险配置失败: {e}")
        
        # 保存默认配置
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存默认风险配置失败: {e}")
        
        return default_config
    
    def check_order(self, account: AccountInfo, order: Order) -> bool:
        """检查订单是否符合风险要求
        
        Args:
            account: 账户信息
            order: 订单信息
            
        Returns:
            bool: 是否符合风险要求
        """
        # 重置每日交易金额
        self._reset_daily_limit()
        
        # 1. 检查余额
        if not self._check_balance(account, order):
            return False
        
        # 2. 检查订单规模
        if not self._check_order_size(order):
            return False
        
        # 3. 检查日交易限额
        if not self._check_daily_limit(order):
            return False
        
        # 4. 检查市场暴露
        if not self._check_market_exposure(order):
            return False
        
        # 5. 检查交易频率
        if not self._check_trade_frequency():
            return False
        
        # 6. 检查价格偏差
        if not self._check_price_deviation(order):
            return False
        
        # 7. 检查持仓规模
        if not self._check_position_size(account):
            return False
        
        # 通过所有风险检查
        return True
    
    def _check_balance(self, account: AccountInfo, order: Order) -> bool:
        """检查账户余额"""
        cost = order.quantity * (order.price or Decimal('1'))
        usdc_balance = account.balances.get("USDC", Decimal('0'))
        return usdc_balance >= cost
    
    def _check_order_size(self, order: Order) -> bool:
        """检查订单规模"""
        order_size = order.quantity * (order.price or Decimal('1'))
        max_order_size = Decimal(str(self.config.get('max_order_size', 1000)))
        return order_size <= max_order_size
    
    def _check_daily_limit(self, order: Order) -> bool:
        """检查日交易限额"""
        order_size = order.quantity * (order.price or Decimal('1'))
        daily_limit = Decimal(str(self.config.get('daily_trade_limit', 10000)))
        return self.daily_trade_amount + order_size <= daily_limit
    
    def _check_market_exposure(self, order: Order) -> bool:
        """检查市场暴露"""
        market_symbol = order.instrument.symbol
        order_size = order.quantity * (order.price or Decimal('1'))
        max_exposure = Decimal(str(self.config.get('max_market_exposure', 5000)))
        
        current_exposure = self.market_exposure.get(market_symbol, Decimal('0'))
        return current_exposure + order_size <= max_exposure
    
    def _check_trade_frequency(self) -> bool:
        """检查交易频率"""
        max_trades = self.config.get('max_trades_per_minute', 10)
        current_time = datetime.now()
        
        # 计算过去一分钟的交易次数
        minute_ago = current_time - timedelta(minutes=1)
        recent_trades = [trade for trade in self.trade_history 
                       if datetime.fromisoformat(trade['timestamp']) >= minute_ago]
        
        return len(recent_trades) < max_trades
    
    def _check_price_deviation(self, order: Order) -> bool:
        """检查价格偏差"""
        # 这里应该从市场获取当前价格
        # 由于实际API可能不同，这里简化处理
        return True
    
    def _check_position_size(self, account: AccountInfo) -> bool:
        """检查持仓规模"""
        max_position = Decimal(str(self.config.get('max_position_size', 10000)))
        total_position = Decimal('0')
        
        for position in account.positions.values():
            position_value = position.size * position.avg_price
            total_position += position_value
        
        return total_position <= max_position
    
    def _reset_daily_limit(self):
        """重置每日交易限额"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trade_amount = Decimal('0')
            self.last_reset_date = today
    
    def record_trade(self, order: Order, executed_price: Decimal):
        """记录交易
        
        Args:
            order: 订单信息
            executed_price: 执行价格
        """
        trade_size = order.quantity * executed_price
        self.daily_trade_amount += trade_size
        
        # 更新市场暴露
        market_symbol = order.instrument.symbol
        if market_symbol not in self.market_exposure:
            self.market_exposure[market_symbol] = Decimal('0')
        
        if order.side.value == 'buy':
            self.market_exposure[market_symbol] += trade_size
        else:
            self.market_exposure[market_symbol] -= trade_size
        
        # 记录交易历史
        trade_record = {
            'order_id': order.order_id,
            'market': market_symbol,
            'side': order.side.value,
            'quantity': order.quantity,
            'price': executed_price,
            'amount': trade_size,
            'timestamp': datetime.now().isoformat()
        }
        self.trade_history.append(trade_record)
        
        # 保持交易历史不超过1000条
        if len(self.trade_history) > 1000:
            self.trade_history.pop(0)
    
    def get_stop_loss_price(self, entry_price: Decimal) -> Decimal:
        """获取止损价格
        
        Args:
            entry_price: 入场价格
            
        Returns:
            Decimal: 止损价格
        """
        stop_loss_percent = Decimal(str(self.config.get('stop_loss_percent', 0.05)))
        return entry_price * (Decimal('1') - stop_loss_percent)
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """获取风险摘要
        
        Returns:
            Dict[str, Any]: 风险摘要
        """
        return {
            'daily_trade_amount': float(self.daily_trade_amount),
            'daily_trade_limit': self.config.get('daily_trade_limit', 10000),
            'market_exposure': {k: float(v) for k, v in self.market_exposure.items()},
            'trade_count_today': len([t for t in self.trade_history 
                                   if datetime.fromisoformat(t['timestamp']).date() == self.last_reset_date]),
            'max_order_size': self.config.get('max_order_size', 1000),
            'price_deviation_threshold': self.config.get('price_deviation_threshold', 0.05)
        }
    
    def update_config(self, config: Dict[str, Any]):
        """更新风险配置
        
        Args:
            config: 新的风险配置
        """
        self.config.update(config)
        
        # 保存配置
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存风险配置失败: {e}")

# 类型提示
from typing import Any
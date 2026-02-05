from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from core.models import Order
from engine.execution_engine import ExecutionEngine
from engine.event_recorder import EventRecorder
from engine.large_order_monitor import LargeOrderMonitor
from engine.liquidity_analyzer import LiquidityAnalyzer
from account.account_manager import AccountManager
from gateways.base import BaseGateway
from utils.logger import logger
import json

class DataService:
    """Data service layer for dashboard"""
    
    def __init__(self):
        """Initialize data service"""
        self.execution_engine: Optional[ExecutionEngine] = None
        self.event_recorder: Optional[EventRecorder] = None
        self.large_order_monitor: Optional[LargeOrderMonitor] = None
        self.liquidity_analyzer: Optional[LiquidityAnalyzer] = None
        self._initialized = False
    
    def initialize(self, execution_engine: ExecutionEngine):
        """Initialize with execution engine"""
        self.execution_engine = execution_engine
        self.event_recorder = execution_engine.event_recorder
        self.large_order_monitor = execution_engine.large_order_monitor
        self.liquidity_analyzer = execution_engine.liquidity_analyzer
        
        self._initialized = True
        logger.info("DataService initialized successfully")
    
    def is_initialized(self) -> bool:
        """Check if data service is initialized"""
        return self._initialized
    
    def get_order_stats(self) -> Dict[str, Any]:
        """Get order statistics"""
        try:
            # 直接从执行引擎获取订单历史
            if not self.execution_engine:
                return {
                    'total_orders': 0,
                    'filled_orders': 0,
                    'pending_orders': 0,
                    'rejected_orders': 0,
                    'total_size': 0
                }
            
            order_history = self.execution_engine.get_order_history()
            total_orders = len(order_history)
            
            # 分析订单状态
            filled_orders = 0
            pending_orders = 0
            rejected_orders = 0
            total_size = 0
            
            for order in order_history:
                status = order.get('status')
                if status == 'filled':
                    filled_orders += 1
                elif status == 'pending':
                    pending_orders += 1
                elif status == 'rejected':
                    rejected_orders += 1
                
                # 计算总订单大小
                try:
                    quantity = Decimal(order.get('quantity', '0'))
                    total_size += quantity
                except Exception:
                    pass
            
            return {
                'total_orders': total_orders,
                'filled_orders': filled_orders,
                'pending_orders': pending_orders,
                'rejected_orders': rejected_orders,
                'total_size': total_size
            }
        except Exception as e:
            logger.error(f"Error getting order stats: {e}")
            return {
                'total_orders': 0,
                'filled_orders': 0,
                'pending_orders': 0,
                'rejected_orders': 0,
                'total_size': 0
            }
    
    def get_order_history(self, page: int = 1, page_size: int = 100) -> List[Dict[str, Any]]:
        """Get order history with pagination"""
        try:
            # 直接从执行引擎获取订单历史
            if not self.execution_engine:
                return []
            
            order_history = self.execution_engine.get_order_history()
            
            # 应用分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            return order_history[start_idx:end_idx]
        except Exception as e:
            logger.error(f"Error getting order history: {e}")
            return []
    
    def get_event_data(self, days: int = 7, page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
        """Get event data"""
        try:
            # 直接从事件记录器获取事件数据
            if not self.event_recorder:
                return []
            
            recent_events = self.event_recorder.get_recent_events(days)
            
            # 应用分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            return recent_events[start_idx:end_idx]
        except Exception as e:
            logger.error(f"Error getting event data: {e}")
            return []
    
    def get_large_orders(self, days: int = 7, page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
        """Get large orders"""
        try:
            # 直接从大额订单监控器获取数据
            if not self.large_order_monitor:
                return []
            
            recent_orders = self.large_order_monitor._get_recent_orders(days)
            
            # 应用分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            return recent_orders[start_idx:end_idx]
        except Exception as e:
            logger.error(f"Error getting large orders: {e}")
            return []
    
    def get_liquidity_analysis(self, symbol: str, size: Decimal) -> Dict[str, Any]:
        """Get liquidity analysis"""
        try:
            if not self.liquidity_analyzer:
                return {
                    'liquidity_rating': 'UNKNOWN',
                    'slippage_estimate': 0.0,
                    'confidence': 'LOW',
                    'message': 'Liquidity analyzer not initialized'
                }
            
            return self.liquidity_analyzer.analyze_liquidity(symbol, size)
        except Exception as e:
            logger.error(f"Error getting liquidity analysis: {e}")
            return {
                'liquidity_rating': 'ERROR',
                'slippage_estimate': 0.0,
                'confidence': 'LOW',
                'message': f'Error: {str(e)}'
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        try:
            # 从执行引擎获取订单历史数量
            order_history_count = 0
            if self.execution_engine:
                order_history = self.execution_engine.get_order_history()
                order_history_count = len(order_history)
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'initialized': self._initialized,
                'components': {
                    'execution_engine': bool(self.execution_engine),
                    'event_recorder': bool(self.event_recorder),
                    'large_order_monitor': bool(self.large_order_monitor),
                    'liquidity_analyzer': bool(self.liquidity_analyzer)
                },
                'order_history_count': order_history_count,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            }
            
            return status
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'initialized': False,
                'components': {
                    'execution_engine': False,
                    'event_recorder': False,
                    'large_order_monitor': False,
                    'liquidity_analyzer': False
                },
                'order_history_count': 0,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'error': str(e)
            }
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get execution engine status"""
        try:
            if not self.execution_engine:
                return {
                    'system_health': 'not_initialized',
                    'components': {},
                    'gateways': []
                }
            
            return self.execution_engine.get_engine_status()
        except Exception as e:
            logger.error(f"Error getting engine status: {e}")
            return {
                'system_health': 'error',
                'components': {},
                'gateways': [],
                'error': str(e)
            }
    
    def save_order(self, order: Dict[str, Any]) -> bool:
        """Save order (不再使用数据库存储)"""
        try:
            # 订单数据现在通过执行引擎和Polymarket API直接处理
            logger.info(f"Order saved: {order.get('order_id')}")
            return True
        except Exception as e:
            logger.error(f"Error saving order: {e}")
            return False
    
    def save_event(self, event: Dict[str, Any]) -> bool:
        """Save event (不再使用数据库存储)"""
        try:
            # 事件数据现在通过事件记录器直接处理
            logger.info(f"Event saved: {event.get('event_name')}")
            return True
        except Exception as e:
            logger.error(f"Error saving event: {e}")
            return False
    
    def save_large_order(self, order: Dict[str, Any]) -> bool:
        """Save large order (不再使用数据库存储)"""
        try:
            # 大额订单数据现在通过大额订单监控器直接处理
            logger.info(f"Large order saved: {order.get('order_id')}")
            return True
        except Exception as e:
            logger.error(f"Error saving large order: {e}")
            return False
    
    def save_account_balance(self, account_id: str, asset: str, balance: Decimal) -> bool:
        """Save account balance (不再使用数据库存储)"""
        try:
            # 账户余额数据现在通过执行引擎和Polymarket API直接处理
            logger.info(f"Account balance saved: {account_id}, {asset}, {balance}")
            return True
        except Exception as e:
            logger.error(f"Error saving account balance: {e}")
            return False

# Create a singleton instance
data_service = DataService()
from typing import Dict, Optional, List, Any, Tuple
from decimal import Decimal
from datetime import datetime
from core.models import Order
from account.account_manager import AccountManager
from gateways.base import BaseGateway
from engine.risk_manager import RiskManager
from engine.liquidity_analyzer import LiquidityAnalyzer
from engine.event_recorder import EventRecorder
from engine.large_order_monitor import LargeOrderMonitor
from engine.monitoring import monitoring_manager, AlertLevel, AlertType
from strategy.probability_strategy import ProbabilityStrategy
from persistence.data_store import data_store
from utils.logger import logger

class ExecutionEngine:
    def __init__(self, account_manager: AccountManager, gateways: Dict[str, BaseGateway]):
        """初始化执行引擎，包含所有必要组件"""
        self.account_manager = account_manager
        self.gateways = gateways
        self.risk_manager = RiskManager()
        self.liquidity_analyzer = LiquidityAnalyzer()
        self.event_recorder = EventRecorder()
        self.large_order_monitor = LargeOrderMonitor()
        self.probability_strategy = ProbabilityStrategy()
        self._order_history: List[Dict[str, Any]] = []
    
    def submit_order(self, order: Order, market_probabilities: Optional[Dict[str, Decimal]] = None) -> Dict[str, Any]:
        """提交单个订单，包含全面的验证和执行流程"""
        result = {
            'order_id': order.order_id,
            'status': 'pending',
            'message': '',
            'steps': []
        }
        
        try:
            # 步骤1: 验证订单
            validation_result = self._validate_order(order)
            if not validation_result['valid']:
                order.status = 'rejected'
                result['status'] = 'rejected'
                result['message'] = validation_result['message']
                result['steps'].append({'step': 'validation', 'status': 'failed', 'message': validation_result['message']})
                logger.warning(f"订单 {order.order_id} 被拒绝: {validation_result['message']}")
                return result
            
            result['steps'].append({'step': 'validation', 'status': 'success'})
            
            # 步骤2: 如果提供了市场数据，检查概率策略
            if market_probabilities:
                prob_analysis = self.probability_strategy.analyze_market_probabilities(market_probabilities)
                if not prob_analysis['can_trade']:
                    order.status = 'rejected'
                    result['status'] = 'rejected'
                    result['message'] = prob_analysis['message']
                    result['steps'].append({'step': 'probability_check', 'status': 'failed', 'message': prob_analysis['message']})
                    logger.warning(f"订单 {order.order_id} 被拒绝: {prob_analysis['message']}")
                    return result
                elif prob_analysis['message']:
                    result['steps'].append({'step': 'probability_check', 'status': 'warning', 'message': prob_analysis['message']})
                    logger.warning(f"订单 {order.order_id} 谨慎执行: {prob_analysis['message']}")
                else:
                    result['steps'].append({'step': 'probability_check', 'status': 'success'})
            
            # 步骤3: 检查风险
            account = self.account_manager.get_account(order.account_id)
            if not self.risk_manager.check_order(account, order):
                order.status = 'rejected'
                result['status'] = 'rejected'
                result['message'] = '风险检查失败'
                result['steps'].append({'step': 'risk_check', 'status': 'failed', 'message': '资金不足或超出风险限制'})
                logger.warning(f"订单 {order.order_id} 被风险管理器拒绝")
                return result
            
            result['steps'].append({'step': 'risk_check', 'status': 'success'})
            
            # 步骤4: 分析流动性
            liquidity_analysis = self.liquidity_analyzer.analyze_liquidity(
                order.instrument.symbol, 
                order.quantity
            )
            
            if liquidity_analysis['liquidity_rating'] == 'LOW':
                result['steps'].append({'step': 'liquidity_analysis', 'status': 'warning', 'message': liquidity_analysis['message']})
                logger.warning(f"{order.instrument.symbol} 流动性较低: {liquidity_analysis['message']}")
            else:
                result['steps'].append({'step': 'liquidity_analysis', 'status': 'success', 'message': liquidity_analysis['message']})
            
            # 步骤5: 记录大额订单（如果适用）
            large_order_info = {
                'order_id': order.order_id,
                'symbol': order.instrument.symbol,
                'side': order.side.value,
                'quantity': order.quantity,
                'price': order.price,
                'account_id': order.account_id,
                'gateway_name': order.instrument.gateway_name
            }
            large_order_recorded = self.large_order_monitor.record_large_order(large_order_info)
            result['steps'].append({'step': 'large_order_check', 'status': 'success', 'recorded': large_order_recorded})
            
            # 步骤6: 执行订单
            gateway_name = order.instrument.gateway_name
            if gateway_name not in self.gateways:
                order.status = 'rejected'
                result['status'] = 'rejected'
                result['message'] = f'网关 {gateway_name} 不可用'
                result['steps'].append({'step': 'execution', 'status': 'failed', 'message': f'网关 {gateway_name} 不可用'})
                logger.error(f"订单 {order.order_id} 的网关 {gateway_name} 未找到")
                return result
            
            gateway = self.gateways[gateway_name]
            gw_order_id = gateway.send_order(order)
            order.gateway_order_id = gw_order_id
            order.status = 'submitted'
            
            result['status'] = 'submitted'
            result['message'] = f'订单提交成功'
            result['gateway_order_id'] = gw_order_id
            result['steps'].append({'step': 'execution', 'status': 'success', 'gateway_order_id': gw_order_id})
            logger.info(f"订单 {order.order_id} 已提交 → {gw_order_id[:10]}...")
            
            # 步骤7: 记录执行为流动性分析
            # 在实际系统中，我们会从网关获取实际执行价格
            executed_price = order.price or Decimal('1')
            self.liquidity_analyzer.add_historical_data(
                order.instrument.symbol,
                datetime.now(),
                executed_price,
                executed_price,  # 模拟无滑点
                order.quantity
            )
            
            # 步骤8: 记录交易到风险管理器
            self.risk_manager.record_trade(order, executed_price)
            
            # 步骤8: 记录订单历史
            self._record_order_history(order, result)
            
        except Exception as e:
            order.status = 'rejected'
            result['status'] = 'error'
            result['message'] = f'意外错误: {str(e)}'
            result['steps'].append({'step': 'execution', 'status': 'error', 'message': str(e)})
            logger.error(f"提交订单 {order.order_id} 错误: {e}")
            
            # 创建告警
            monitoring_manager.create_alert(
                AlertLevel.ERROR,
                AlertType.ORDER,
                f"提交订单 {order.order_id} 错误: {str(e)}",
                {
                    'order_id': order.order_id,
                    'instrument': order.instrument.symbol,
                    'quantity': float(order.quantity),
                    'price': float(order.price or 0),
                    'error': str(e)
                }
            )
        
        return result
    
    def submit_orders_batch(self, orders: List[Tuple[Order, Optional[Dict[str, Decimal]]]]) -> Dict[str, Any]:
        """批量提交多个订单以提高性能"""
        results = {
            'total': len(orders),
            'submitted': 0,
            'rejected': 0,
            'errors': 0,
            'details': []
        }
        
        for order, market_probabilities in orders:
            try:
                result = self.submit_order(order, market_probabilities)
                results['details'].append(result)
                
                if result['status'] == 'submitted':
                    results['submitted'] += 1
                elif result['status'] == 'rejected':
                    results['rejected'] += 1
                else:
                    results['errors'] += 1
            except Exception as e:
                results['errors'] += 1
                results['details'].append({
                    'order_id': order.order_id,
                    'status': 'error',
                    'message': str(e)
                })
                logger.error(f"处理批量订单 {order.order_id} 错误: {e}")
                
                # 创建告警
                monitoring_manager.create_alert(
                    AlertLevel.ERROR,
                    AlertType.ORDER,
                    f"处理批量订单 {order.order_id} 错误: {str(e)}",
                    {
                        'order_id': order.order_id,
                        'error': str(e)
                    }
                )
        
        return results
    
    def _validate_order(self, order: Order) -> Dict[str, Any]:
        """提交前验证订单"""
        if not order:
            return {'valid': False, 'message': '订单不能为空'}
        
        if not order.order_id:
            return {'valid': False, 'message': '订单ID是必需的'}
        
        if not order.instrument:
            return {'valid': False, 'message': '交易品种是必需的'}
        
        if not order.side:
            return {'valid': False, 'message': '订单方向是必需的'}
        
        if not order.type:
            return {'valid': False, 'message': '订单类型是必需的'}
        
        if order.quantity <= Decimal('0'):
            return {'valid': False, 'message': '订单数量必须为正数'}
        
        if order.instrument.gateway_name not in self.gateways:
            return {'valid': False, 'message': f'网关 {order.instrument.gateway_name} 不可用'}
        
        return {'valid': True, 'message': '订单验证成功'}
    
    def _record_order_history(self, order: Order, result: Dict[str, Any]):
        """记录订单历史用于审计和分析"""
        try:
            history_entry = {
                'timestamp': datetime.now().isoformat(),
                'order_id': order.order_id,
                'instrument': order.instrument.symbol,
                'side': order.side.value,
                'type': order.type.value,
                'quantity': str(order.quantity),
                'price': str(order.price) if order.price else None,
                'account_id': order.account_id,
                'status': order.status,
                'gateway_order_id': order.gateway_order_id,
                'execution_result': result
            }
            
            # 管理历史记录大小
            if len(self._order_history) >= 10000:  # 限制为10,000个订单
                self._order_history.pop(0)
            
            self._order_history.append(history_entry)
            
            # 保存到数据库
            try:
                order_data = {
                    'order_id': order.order_id,
                    'instrument': {'symbol': order.instrument.symbol},
                    'side': order.side.value,
                    'type': order.type.value,
                    'quantity': order.quantity,
                    'price': order.price,
                    'status': order.status,
                    'filled_qty': order.filled_qty,
                    'gateway_order_id': order.gateway_order_id,
                    'account_id': order.account_id,
                    'outcome': order.outcome
                }
                
                saved = data_store.save_order(order_data, result)
                if saved:
                    logger.info(f"订单 {order.order_id} 已保存到数据库")
                else:
                    logger.error(f"保存订单 {order.order_id} 到数据库失败")
            except Exception as db_error:
                logger.error(f"保存订单到数据库错误: {db_error}")
        except Exception as e:
            logger.error(f"记录订单历史错误: {e}")
    
    def sync_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """同步订单状态
        
        Args:
            order_id: 订单ID
            
        Returns:
            Optional[Dict[str, Any]]: 订单状态信息
        """
        try:
            # 查找订单
            for order_entry in self._order_history:
                if order_entry['order_id'] == order_id:
                    gateway_name = order_entry.get('gateway_name', 'polymarket')
                    gateway_order_id = order_entry.get('gateway_order_id')
                    
                    if gateway_name in self.gateways and gateway_order_id:
                        gateway = self.gateways[gateway_name]
                        # 从网关获取订单状态
                        order_status = gateway.get_order_status(gateway_order_id)
                        
                        if order_status:
                            # 更新订单状态
                            order_status['order_id'] = order_id
                            order_status['gateway_order_id'] = gateway_order_id
                            return order_status
            
            return None
        except Exception as e:
            logger.error(f"同步订单状态错误: {e}")
            return None
    
    def sync_all_orders(self) -> Dict[str, Any]:
        """同步所有活跃订单的状态
        
        Returns:
            Dict[str, Any]: 同步结果
        """
        try:
            results = {
                'total': 0,
                'updated': 0,
                'errors': 0,
                'details': []
            }
            
            # 获取活跃订单
            active_orders = [order for order in self._order_history 
                           if order['status'] in ['submitted', 'partially_filled']]
            
            results['total'] = len(active_orders)
            
            for order_entry in active_orders:
                try:
                    order_status = self.sync_order_status(order_entry['order_id'])
                    if order_status:
                        results['updated'] += 1
                        results['details'].append(order_status)
                except Exception as e:
                    results['errors'] += 1
                    results['details'].append({
                        'order_id': order_entry['order_id'],
                        'error': str(e)
                    })
            
            return results
        except Exception as e:
            logger.error(f"同步所有订单状态错误: {e}")
            return {
                'total': 0,
                'updated': 0,
                'errors': 1,
                'details': [{'error': str(e)}]
            }
    
    def record_event_data(self, event_name: str, data: Dict[str, Any]):
        """记录事件数据，增强错误处理"""
        try:
            success = self.event_recorder.record_event_data(event_name, datetime.now(), data)
            if success:
                logger.info(f"事件数据已记录: {event_name}")
            else:
                logger.warning(f"事件数据记录失败: {event_name}")
            
            # 保存到数据存储
            saved = data_store.save_event(event_name, data)
            if saved:
                logger.info(f"事件 {event_name} 已保存到数据存储")
            else:
                logger.error(f"保存事件到数据存储失败: {event_name}")
        except Exception as e:
            logger.error(f"记录事件数据错误: {e}")
    
    def record_events_batch(self, events: List[Tuple[str, Dict[str, Any]]]):
        """批量记录多个事件"""
        try:
            event_tuples = [(event_name, datetime.now(), data) for event_name, data in events]
            result = self.event_recorder.record_events_batch(event_tuples)
            logger.info(f"批量事件记录完成: {result}")
            return result
        except Exception as e:
            logger.error(f"批量事件记录错误: {e}")
            return {'total': len(events), 'success': 0, 'failed': len(events), 'errors': [str(e)]}
    
    def get_liquidity_analysis(self, symbol: str, size: Decimal) -> Dict[str, Any]:
        """获取流动性分析，包含错误处理"""
        try:
            return self.liquidity_analyzer.analyze_liquidity(symbol, size)
        except Exception as e:
            logger.error(f"获取流动性分析错误: {e}")
            return {
                'liquidity_rating': 'LOW',
                'slippage_estimate': Decimal('0.01'),
                'confidence': 'LOW',
                'message': f'分析过程错误: {str(e)}'
            }
    
    def get_large_orders_summary(self, days: int = 7) -> Dict[str, Any]:
        """获取大额订单摘要，包含错误处理"""
        try:
            return self.large_order_monitor.get_large_orders_summary(days)
        except Exception as e:
            logger.error(f"获取大额订单摘要错误: {e}")
            return {
                'total_large_orders': 0,
                'by_symbol': {},
                'by_side': {},
                'by_account': {},
                'total_quantity': Decimal('0'),
                'average_quantity': Decimal('0'),
                'error': str(e)
            }
    
    def get_order_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的订单历史"""
        return self._order_history[-limit:]
    
    def get_engine_status(self) -> Dict[str, Any]:
        """获取全面的引擎状态"""
        try:
            status = {
                'timestamp': datetime.now().isoformat(),
                'components': {
                    'risk_manager': 'active',
                    'liquidity_analyzer': 'active',
                    'event_recorder': 'active',
                    'large_order_monitor': 'active',
                    'probability_strategy': 'active'
                },
                'gateways': list(self.gateways.keys()),
                'order_history_count': len(self._order_history),
                'system_health': 'healthy'
            }
            
            # 添加组件特定状态
            status['components']['large_order_monitor'] = {
                'status': 'active',
                'threshold': str(self.large_order_monitor.threshold)
            }
            
            return status
        except Exception as e:
            logger.error(f"获取引擎状态错误: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'system_health': 'error',
                'error': str(e)
            }


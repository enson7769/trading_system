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
from strategy.probability_strategy import ProbabilityStrategy
from utils.logger import logger

class ExecutionEngine:
    def __init__(self, account_manager: AccountManager, gateways: Dict[str, BaseGateway]):
        """Initialize execution engine with all required components"""
        self.account_manager = account_manager
        self.gateways = gateways
        self.risk_manager = RiskManager()
        self.liquidity_analyzer = LiquidityAnalyzer()
        self.event_recorder = EventRecorder()
        self.large_order_monitor = LargeOrderMonitor()
        self.probability_strategy = ProbabilityStrategy()
        self._order_history: List[Dict[str, Any]] = []
    
    def submit_order(self, order: Order, market_probabilities: Optional[Dict[str, Decimal]] = None) -> Dict[str, Any]:
        """Submit a single order with comprehensive validation and execution"""
        result = {
            'order_id': order.order_id,
            'status': 'pending',
            'message': '',
            'steps': []
        }
        
        try:
            # Step 1: Validate order
            validation_result = self._validate_order(order)
            if not validation_result['valid']:
                order.status = 'rejected'
                result['status'] = 'rejected'
                result['message'] = validation_result['message']
                result['steps'].append({'step': 'validation', 'status': 'failed', 'message': validation_result['message']})
                logger.warning(f"Order {order.order_id} rejected: {validation_result['message']}")
                return result
            
            result['steps'].append({'step': 'validation', 'status': 'success'})
            
            # Step 2: Check probability strategy if market data provided
            if market_probabilities:
                prob_analysis = self.probability_strategy.analyze_market_probabilities(market_probabilities)
                if not prob_analysis['can_trade']:
                    order.status = 'rejected'
                    result['status'] = 'rejected'
                    result['message'] = prob_analysis['message']
                    result['steps'].append({'step': 'probability_check', 'status': 'failed', 'message': prob_analysis['message']})
                    logger.warning(f"Order {order.order_id} rejected: {prob_analysis['message']}")
                    return result
                elif prob_analysis['message']:
                    result['steps'].append({'step': 'probability_check', 'status': 'warning', 'message': prob_analysis['message']})
                    logger.warning(f"Order {order.order_id} proceeding with caution: {prob_analysis['message']}")
                else:
                    result['steps'].append({'step': 'probability_check', 'status': 'success'})
            
            # Step 3: Check risk
            account = self.account_manager.get_account(order.account_id)
            if not self.risk_manager.check_order(account, order):
                order.status = 'rejected'
                result['status'] = 'rejected'
                result['message'] = 'Risk check failed'
                result['steps'].append({'step': 'risk_check', 'status': 'failed', 'message': 'Insufficient funds or risk limit exceeded'})
                logger.warning(f"Order {order.order_id} rejected by risk manager")
                return result
            
            result['steps'].append({'step': 'risk_check', 'status': 'success'})
            
            # Step 4: Analyze liquidity
            liquidity_analysis = self.liquidity_analyzer.analyze_liquidity(
                order.instrument.symbol, 
                order.quantity
            )
            
            if liquidity_analysis['liquidity_rating'] == 'LOW':
                result['steps'].append({'step': 'liquidity_analysis', 'status': 'warning', 'message': liquidity_analysis['message']})
                logger.warning(f"Low liquidity for {order.instrument.symbol}: {liquidity_analysis['message']}")
            else:
                result['steps'].append({'step': 'liquidity_analysis', 'status': 'success', 'message': liquidity_analysis['message']})
            
            # Step 5: Record large order if applicable
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
            
            # Step 6: Execute order
            gateway_name = order.instrument.gateway_name
            if gateway_name not in self.gateways:
                order.status = 'rejected'
                result['status'] = 'rejected'
                result['message'] = f'Gateway {gateway_name} not available'
                result['steps'].append({'step': 'execution', 'status': 'failed', 'message': f'Gateway {gateway_name} not available'})
                logger.error(f"Gateway {gateway_name} not found for order {order.order_id}")
                return result
            
            gateway = self.gateways[gateway_name]
            gw_order_id = gateway.send_order(order)
            order.gateway_order_id = gw_order_id
            order.status = 'submitted'
            
            result['status'] = 'submitted'
            result['message'] = f'Order submitted successfully'
            result['gateway_order_id'] = gw_order_id
            result['steps'].append({'step': 'execution', 'status': 'success', 'gateway_order_id': gw_order_id})
            logger.info(f"Order {order.order_id} submitted → {gw_order_id[:10]}...")
            
            # Step 7: Record execution for liquidity analysis
            # In a real system, we would get the actual executed price from the gateway
            self.liquidity_analyzer.add_historical_data(
                order.instrument.symbol,
                datetime.now(),
                order.price or Decimal('1'),
                order.price or Decimal('1'),  # Simulating no slippage for demo
                order.quantity
            )
            
            # Step 8: Record order history
            self._record_order_history(order, result)
            
        except Exception as e:
            order.status = 'rejected'
            result['status'] = 'error'
            result['message'] = f'Unexpected error: {str(e)}'
            result['steps'].append({'step': 'execution', 'status': 'error', 'message': str(e)})
            logger.error(f"Error submitting order {order.order_id}: {e}")
        
        return result
    
    def submit_orders_batch(self, orders: List[Tuple[Order, Optional[Dict[str, Decimal]]]]) -> Dict[str, Any]:
        """Submit multiple orders in batch for improved performance"""
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
                logger.error(f"Error processing batch order {order.order_id}: {e}")
        
        return results
    
    def _validate_order(self, order: Order) -> Dict[str, Any]:
        """Validate order before submission"""
        if not order:
            return {'valid': False, 'message': 'Order cannot be None'}
        
        if not order.order_id:
            return {'valid': False, 'message': 'Order ID is required'}
        
        if not order.instrument:
            return {'valid': False, 'message': 'Instrument is required'}
        
        if not order.side:
            return {'valid': False, 'message': 'Order side is required'}
        
        if not order.type:
            return {'valid': False, 'message': 'Order type is required'}
        
        if order.quantity <= Decimal('0'):
            return {'valid': False, 'message': 'Order quantity must be positive'}
        
        if order.instrument.gateway_name not in self.gateways:
            return {'valid': False, 'message': f'Gateway {order.instrument.gateway_name} not available'}
        
        return {'valid': True, 'message': 'Order validation successful'}
    
    def _record_order_history(self, order: Order, result: Dict[str, Any]):
        """Record order history for audit and analysis"""
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
            
            # Manage history size
            if len(self._order_history) >= 10000:  # Limit to 10,000 orders
                self._order_history.pop(0)
            
            self._order_history.append(history_entry)
            
            # Save to database
            try:
                # Lazy import to avoid circular import
                from dashboard.data_service import data_service
                
                order_data = {
                    'order_id': order.order_id,
                    'account_id': order.account_id,
                    'instrument': order.instrument.symbol,
                    'side': order.side.value,
                    'type': order.type.value,
                    'quantity': order.quantity,
                    'price': order.price,
                    'status': order.status,
                    'filled_qty': 0,  # Default to 0, update when order is filled
                    'gateway_order_id': order.gateway_order_id
                }
                data_service.save_order(order_data)
                logger.info(f"Order {order.order_id} saved to database")
            except Exception as db_error:
                logger.error(f"Error saving order to database: {db_error}")
        except Exception as e:
            logger.error(f"Error recording order history: {e}")
    
    def record_event_data(self, event_name: str, data: Dict[str, Any]):
        """Record event data with enhanced error handling"""
        try:
            success = self.event_recorder.record_event_data(event_name, datetime.now(), data)
            if success:
                logger.info(f"Event data recorded for {event_name}")
            else:
                logger.warning(f"Failed to record event data for {event_name}")
            
            # Save to database
            try:
                # Lazy import to avoid circular import
                from dashboard.data_service import data_service
                
                event_data = {
                    'event_name': event_name,
                    'timestamp': datetime.now(),
                    'data': data
                }
                data_service.save_event(event_data)
                logger.info(f"Event {event_name} saved to database")
            except Exception as db_error:
                logger.error(f"Error saving event to database: {db_error}")
        except Exception as e:
            logger.error(f"Error recording event data: {e}")
    
    def record_events_batch(self, events: List[Tuple[str, Dict[str, Any]]]):
        """Record multiple events in batch"""
        try:
            event_tuples = [(event_name, datetime.now(), data) for event_name, data in events]
            result = self.event_recorder.record_events_batch(event_tuples)
            logger.info(f"Batch event recording completed: {result}")
            return result
        except Exception as e:
            logger.error(f"Error in batch event recording: {e}")
            return {'total': len(events), 'success': 0, 'failed': len(events), 'errors': [str(e)]}
    
    def get_liquidity_analysis(self, symbol: str, size: Decimal) -> Dict[str, Any]:
        """Get liquidity analysis with error handling"""
        try:
            return self.liquidity_analyzer.analyze_liquidity(symbol, size)
        except Exception as e:
            logger.error(f"Error getting liquidity analysis: {e}")
            return {
                'liquidity_rating': 'LOW',
                'slippage_estimate': Decimal('0.01'),
                'confidence': 'LOW',
                'message': f'Error during analysis: {str(e)}'
            }
    
    def get_large_orders_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get large orders summary with error handling"""
        try:
            return self.large_order_monitor.get_large_orders_summary(days)
        except Exception as e:
            logger.error(f"Error getting large orders summary: {e}")
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
        """Get recent order history"""
        return self._order_history[-limit:]
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get comprehensive engine status"""
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
            
            # Add component-specific status
            status['components']['large_order_monitor'] = {
                'status': 'active',
                'threshold': str(self.large_order_monitor.threshold)
            }
            
            return status
        except Exception as e:
            logger.error(f"Error getting engine status: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'system_health': 'error',
                'error': str(e)
            }


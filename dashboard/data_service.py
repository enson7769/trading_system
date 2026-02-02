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
from database.database_manager import db_manager
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
        
        # Initialize database
        try:
            # Connect to database
            if not db_manager.connect():
                logger.error("Failed to connect to database")
            
            # Initialize database schema
            if not db_manager.initialize_database():
                logger.error("Failed to initialize database schema")
            
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
        
        self._initialized = True
        logger.info("DataService initialized successfully")
    
    def is_initialized(self) -> bool:
        """Check if data service is initialized"""
        return self._initialized
    
    def get_order_stats(self) -> Dict[str, Any]:
        """Get order statistics"""
        try:
            # Try to get stats from database first
            result = db_manager.execute_query("""
                SELECT 
                    COUNT(*) AS total_orders,
                    SUM(CASE WHEN status = 'FILLED' THEN 1 ELSE 0 END) AS filled_orders,
                    SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_orders,
                    SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected_orders,
                    SUM(quantity) AS total_size
                FROM orders
            """)
            
            if result and len(result) > 0:
                stats = result[0]
                return {
                    'total_orders': stats.get('total_orders', 0),
                    'filled_orders': stats.get('filled_orders', 0),
                    'pending_orders': stats.get('pending_orders', 0),
                    'rejected_orders': stats.get('rejected_orders', 0),
                    'total_size': stats.get('total_size', 0)
                }
            
            # Fallback to execution engine if database fails
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
            
            # Analyze order statuses
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
                
                # Add to total size
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
            # Try to get order history from database first
            offset = (page - 1) * page_size
            result = db_manager.execute_query("""
                SELECT 
                    o.order_id,
                    o.account_id,
                    i.symbol AS instrument,
                    o.side,
                    o.type,
                    o.quantity,
                    o.price,
                    o.status,
                    o.filled_qty,
                    o.gateway_order_id,
                    o.created_at AS timestamp
                FROM orders o
                JOIN instruments i ON o.instrument_id = i.id
                ORDER BY o.created_at DESC
                LIMIT %s OFFSET %s
            """, (page_size, offset))
            
            if result:
                # Convert to the expected format
                orders = []
                for row in result:
                    order = {
                        'order_id': row['order_id'],
                        'account_id': row['account_id'],
                        'instrument': row['instrument'],
                        'side': row['side'],
                        'type': row['type'],
                        'quantity': str(row['quantity']),
                        'price': str(row['price']) if row['price'] else None,
                        'status': row['status'].lower(),
                        'filled_qty': str(row['filled_qty']),
                        'gateway_order_id': row['gateway_order_id'],
                        'timestamp': row['timestamp'].isoformat()
                    }
                    orders.append(order)
                return orders
            
            # Fallback to execution engine if database fails
            if not self.execution_engine:
                return []
            
            order_history = self.execution_engine.get_order_history()
            
            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            return order_history[start_idx:end_idx]
        except Exception as e:
            logger.error(f"Error getting order history: {e}")
            return []
    
    def get_event_data(self, days: int = 7, page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
        """Get event data"""
        try:
            # Try to get event data from database first
            offset = (page - 1) * page_size
            result = db_manager.execute_query("""
                SELECT 
                    event_name,
                    timestamp,
                    data
                FROM events
                WHERE timestamp >= NOW() - INTERVAL %s DAY
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
            """, (days, page_size, offset))
            
            if result:
                # Convert to the expected format
                events = []
                for row in result:
                    event = {
                        'event_name': row['event_name'],
                        'timestamp': row['timestamp'].isoformat(),
                        'data': json.loads(row['data']) if isinstance(row['data'], str) else row['data']
                    }
                    events.append(event)
                return events
            
            # Fallback to event recorder if database fails
            if not self.event_recorder:
                return []
            
            recent_events = self.event_recorder.get_recent_events(days)
            
            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            return recent_events[start_idx:end_idx]
        except Exception as e:
            logger.error(f"Error getting event data: {e}")
            return []
    
    def get_large_orders(self, days: int = 7, page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
        """Get large orders"""
        try:
            # Try to get large orders from database first
            offset = (page - 1) * page_size
            result = db_manager.execute_query("""
                SELECT 
                    lo.order_id,
                    lo.account_id,
                    i.symbol AS symbol,
                    lo.side,
                    lo.quantity,
                    lo.price,
                    lo.gateway_name,
                    lo.recorded_at AS timestamp
                FROM large_orders lo
                JOIN instruments i ON lo.instrument_id = i.id
                WHERE lo.recorded_at >= NOW() - INTERVAL %s DAY
                ORDER BY lo.recorded_at DESC
                LIMIT %s OFFSET %s
            """, (days, page_size, offset))
            
            if result:
                # Convert to the expected format
                large_orders = []
                for row in result:
                    order = {
                        'order_id': row['order_id'],
                        'account_id': row['account_id'],
                        'symbol': row['symbol'],
                        'side': row['side'],
                        'quantity': str(row['quantity']),
                        'price': str(row['price']) if row['price'] else None,
                        'gateway_name': row['gateway_name'],
                        'timestamp': row['timestamp'].isoformat()
                    }
                    large_orders.append(order)
                return large_orders
            
            # Fallback to large order monitor if database fails
            if not self.large_order_monitor:
                return []
            
            recent_orders = self.large_order_monitor._get_recent_orders(days)
            
            # Apply pagination
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
            # Get order history count from database
            order_history_count = 0
            result = db_manager.execute_query("SELECT COUNT(*) AS count FROM orders")
            if result and len(result) > 0:
                order_history_count = result[0].get('count', 0)
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'initialized': self._initialized,
                'database_connected': db_manager.is_connected(),
                'components': {
                    'execution_engine': bool(self.execution_engine),
                    'event_recorder': bool(self.event_recorder),
                    'large_order_monitor': bool(self.large_order_monitor),
                    'liquidity_analyzer': bool(self.liquidity_analyzer),
                    'database': db_manager.is_connected()
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
                'database_connected': db_manager.is_connected(),
                'components': {
                    'execution_engine': False,
                    'event_recorder': False,
                    'large_order_monitor': False,
                    'liquidity_analyzer': False,
                    'database': db_manager.is_connected()
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
        """Save order to database"""
        try:
            # Get instrument ID
            instrument_id = self._get_instrument_id(order.get('instrument', '0x1234...abcd'))
            
            # Insert order
            query = """
                INSERT INTO orders 
                (order_id, account_id, instrument_id, side, type, quantity, price, status, filled_qty, gateway_order_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    filled_qty = VALUES(filled_qty),
                    gateway_order_id = VALUES(gateway_order_id),
                    updated_at = CURRENT_TIMESTAMP
            """
            
            params = (
                order.get('order_id'),
                order.get('account_id', 'main_account'),
                instrument_id,
                order.get('side', 'BUY').upper(),
                order.get('type', 'LIMIT').upper(),
                order.get('quantity', 0),
                order.get('price'),
                order.get('status', 'PENDING').upper(),
                order.get('filled_qty', 0),
                order.get('gateway_order_id')
            )
            
            affected_rows = db_manager.execute_update(query, params)
            return affected_rows > 0
        except Exception as e:
            logger.error(f"Error saving order: {e}")
            return False
    
    def save_event(self, event: Dict[str, Any]) -> bool:
        """Save event to database"""
        try:
            query = """
                INSERT INTO events (event_name, timestamp, data)
                VALUES (%s, %s, %s)
            """
            
            params = (
                event.get('event_name'),
                event.get('timestamp', datetime.now()),
                json.dumps(event.get('data', {}))
            )
            
            affected_rows = db_manager.execute_update(query, params)
            return affected_rows > 0
        except Exception as e:
            logger.error(f"Error saving event: {e}")
            return False
    
    def save_large_order(self, order: Dict[str, Any]) -> bool:
        """Save large order to database"""
        try:
            # Get instrument ID
            instrument_id = self._get_instrument_id(order.get('symbol', '0x1234...abcd'))
            
            query = """
                INSERT INTO large_orders 
                (order_id, instrument_id, account_id, side, quantity, price, gateway_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                order.get('order_id'),
                instrument_id,
                order.get('account_id', 'main_account'),
                order.get('side', 'BUY').upper(),
                order.get('quantity', 0),
                order.get('price'),
                order.get('gateway_name', 'polymarket')
            )
            
            affected_rows = db_manager.execute_update(query, params)
            return affected_rows > 0
        except Exception as e:
            logger.error(f"Error saving large order: {e}")
            return False
    
    def save_account_balance(self, account_id: str, asset: str, balance: Decimal) -> bool:
        """Save account balance to database"""
        try:
            # Ensure account exists
            self._ensure_account_exists(account_id)
            
            query = """
                INSERT INTO account_balances (account_id, asset, balance)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    balance = VALUES(balance),
                    updated_at = CURRENT_TIMESTAMP
            """
            
            params = (account_id, asset, balance)
            
            affected_rows = db_manager.execute_update(query, params)
            return affected_rows > 0
        except Exception as e:
            logger.error(f"Error saving account balance: {e}")
            return False
    
    def _get_instrument_id(self, symbol: str) -> int:
        """Get instrument ID from symbol"""
        try:
            result = db_manager.execute_query(
                "SELECT id FROM instruments WHERE symbol = %s",
                (symbol,)
            )
            
            if result and len(result) > 0:
                return result[0]['id']
            
            # Create instrument if not exists
            query = """
                INSERT INTO instruments (symbol, base_asset, quote_asset, min_order_size, tick_size, gateway_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            params = (symbol, 'USDC', 'USDC', 1, 0.01, 'polymarket')
            db_manager.execute_update(query, params)
            
            return db_manager.get_last_insert_id()
        except Exception as e:
            logger.error(f"Error getting instrument ID: {e}")
            return 1  # Default to first instrument
    
    def _ensure_account_exists(self, account_id: str) -> bool:
        """Ensure account exists in database"""
        try:
            result = db_manager.execute_query(
                "SELECT account_id FROM accounts WHERE account_id = %s",
                (account_id,)
            )
            
            if result and len(result) > 0:
                return True
            
            # Create account if not exists
            query = "INSERT INTO accounts (account_id, gateway_name) VALUES (%s, %s)"
            params = (account_id, 'polymarket')
            db_manager.execute_update(query, params)
            
            return True
        except Exception as e:
            logger.error(f"Error ensuring account exists: {e}")
            return False

# Create a singleton instance
data_service = DataService()
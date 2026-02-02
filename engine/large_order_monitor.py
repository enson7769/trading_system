from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import os
import concurrent.futures
from utils.logger import logger

class LargeOrderMonitor:
    def __init__(self, 
                 threshold: Decimal = Decimal('100'), 
                 data_dir: str = 'data/large_orders',
                 max_memory_orders: int = 1000,
                 max_workers: int = 4):
        """Initialize large order monitor with performance optimizations"""
        # Validate threshold
        if threshold <= Decimal('0'):
            raise ValueError("Threshold must be positive")
        
        self.threshold = threshold
        self.data_dir = data_dir
        self.max_memory_orders = max_memory_orders
        self.max_workers = max_workers
        
        os.makedirs(self.data_dir, exist_ok=True)
        self.large_orders: List[Dict[str, Any]] = []
        self._order_index: Dict[str, List[str]] = {}  # symbol -> list of filenames
        self._build_index()
    
    def _build_index(self) -> None:
        """Build in-memory index for faster lookups"""
        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.data_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            order_data = json.load(f)
                        symbol = order_data.get('symbol')
                        if symbol:
                            if symbol not in self._order_index:
                                self._order_index[symbol] = []
                            self._order_index[symbol].append(filename)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error building order index: {e}")
    
    def set_threshold(self, threshold: Decimal) -> bool:
        """Dynamically update the large order threshold"""
        try:
            if threshold <= Decimal('0'):
                raise ValueError("Threshold must be positive")
            self.threshold = threshold
            logger.info(f"Updated large order threshold to {threshold}")
            return True
        except Exception as e:
            logger.error(f"Error setting threshold: {e}")
            return False
    
    def check_large_order(self, order: Dict[str, Any]) -> bool:
        """Check if an order is considered large"""
        try:
            quantity = order.get('quantity')
            if quantity is None:
                return False
            
            # Handle different types of quantity values
            if isinstance(quantity, str):
                quantity = Decimal(quantity)
            elif not isinstance(quantity, Decimal):
                quantity = Decimal(str(quantity))
            
            return quantity >= self.threshold
        except Exception as e:
            logger.error(f"Error checking large order: {e}")
            return False
    
    def record_large_order(self, order: Dict[str, Any]) -> bool:
        """Record a large order with error handling"""
        try:
            if not self.check_large_order(order):
                return False
            
            # Validate required fields
            if not order.get('order_id'):
                logger.warning("Missing order_id for large order")
            
            order_data = {
                'timestamp': datetime.now().isoformat(),
                'order_id': order.get('order_id'),
                'symbol': order.get('symbol'),
                'side': order.get('side'),
                'quantity': str(order.get('quantity')),
                'price': str(order.get('price')) if order.get('price') else None,
                'account_id': order.get('account_id'),
                'gateway_name': order.get('gateway_name')
            }
            
            # Manage memory usage
            if len(self.large_orders) >= self.max_memory_orders:
                self.large_orders.pop(0)  # Remove oldest order
            self.large_orders.append(order_data)
            
            # Write to file with error handling
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Include milliseconds
            filename = f"large_order_{timestamp}.json"
            filepath = os.path.join(self.data_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(order_data, f, indent=2, ensure_ascii=False)
            
            # Update index
            symbol = order.get('symbol')
            if symbol:
                if symbol not in self._order_index:
                    self._order_index[symbol] = []
                self._order_index[symbol].append(filename)
            
            # Save to database
            try:
                # Lazy import to avoid circular import
                from dashboard.data_service import data_service
                
                db_order_data = {
                    'order_id': order.get('order_id'),
                    'account_id': order.get('account_id'),
                    'symbol': order.get('symbol'),
                    'side': order.get('side'),
                    'quantity': order.get('quantity'),
                    'price': order.get('price'),
                    'gateway_name': order.get('gateway_name')
                }
                data_service.save_large_order(db_order_data)
                logger.info(f"Large order {order.get('order_id')} saved to database")
            except Exception as db_error:
                logger.error(f"Error saving large order to database: {db_error}")
            
            logger.info(f"Recorded large order: {order.get('order_id')} for {order.get('quantity')} units")
            return True
            
        except Exception as e:
            logger.error(f"Error recording large order: {e}")
            return False
    
    def record_orders_batch(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Record multiple orders in batch for improved performance"""
        results = {
            'total': len(orders),
            'large_orders': 0,
            'recorded': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            # First identify large orders
            large_orders_to_record = []
            for order in orders:
                if self.check_large_order(order):
                    results['large_orders'] += 1
                    large_orders_to_record.append(order)
            
            # Record large orders in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.record_large_order, order): order
                    for order in large_orders_to_record
                }
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        success = future.result()
                        if success:
                            results['recorded'] += 1
                        else:
                            results['failed'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(str(e))
        
        except Exception as e:
            logger.error(f"Error in batch recording: {e}")
            results['errors'].append(str(e))
        
        return results
    
    def get_large_orders_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get summary of large orders with improved performance"""
        summary = {
            'total_large_orders': 0,
            'by_symbol': {},
            'by_side': {},
            'by_account': {},
            'total_quantity': Decimal('0'),
            'average_quantity': Decimal('0'),
            'period': f'{days} days'
        }
        
        try:
            recent_orders = self._get_recent_orders(days)
            summary['total_large_orders'] = len(recent_orders)
            
            for order in recent_orders:
                # Symbol analysis
                symbol = order.get('symbol')
                if symbol:
                    summary['by_symbol'][symbol] = summary['by_symbol'].get(symbol, 0) + 1
                
                # Side analysis
                side = order.get('side')
                if side:
                    summary['by_side'][side] = summary['by_side'].get(side, 0) + 1
                
                # Account analysis
                account_id = order.get('account_id')
                if account_id:
                    summary['by_account'][account_id] = summary['by_account'].get(account_id, 0) + 1
                
                # Quantity analysis
                quantity_str = order.get('quantity', '0')
                try:
                    quantity = Decimal(quantity_str)
                    summary['total_quantity'] += quantity
                except Exception:
                    pass
            
            # Calculate average quantity
            if summary['total_large_orders'] > 0:
                summary['average_quantity'] = summary['total_quantity'] / Decimal(str(summary['total_large_orders']))
        
        except Exception as e:
            logger.error(f"Error getting large orders summary: {e}")
            summary['error'] = str(e)
        
        return summary
    
    def _get_recent_orders(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent large orders with parallel processing"""
        recent_orders = []
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        try:
            # Collect all relevant files
            relevant_files = []
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.json'):
                    relevant_files.append(filename)
            
            # Process files in parallel
            def process_file(filename: str) -> Optional[Dict[str, Any]]:
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        order_data = json.load(f)
                    order_time = datetime.fromisoformat(order_data['timestamp']).timestamp()
                    if order_time >= cutoff_time:
                        return order_data
                except Exception as e:
                    logger.error(f"Error reading order file {filename}: {e}")
                return None
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                results = executor.map(process_file, relevant_files)
                for result in results:
                    if result:
                        recent_orders.append(result)
        
        except Exception as e:
            logger.error(f"Error getting recent orders: {e}")
        
        return recent_orders
    
    def get_large_orders_by_symbol(self, symbol: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get large orders for a specific symbol"""
        try:
            # Use index for faster lookup
            if symbol not in self._order_index:
                return []
            
            recent_orders = []
            cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            for filename in self._order_index.get(symbol, []):
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        order_data = json.load(f)
                    order_time = datetime.fromisoformat(order_data['timestamp']).timestamp()
                    if order_time >= cutoff_time:
                        recent_orders.append(order_data)
                except Exception:
                    pass
            
            # Sort by timestamp (newest first)
            recent_orders.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return recent_orders
        
        except Exception as e:
            logger.error(f"Error getting orders by symbol: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about large orders"""
        try:
            stats = {
                'current_threshold': str(self.threshold),
                'memory_orders_count': len(self.large_orders),
                'indexed_symbols': len(self._order_index),
                'total_files': 0,
                'last_updated': datetime.now().isoformat()
            }
            
            # Count total files
            stats['total_files'] = len([f for f in os.listdir(self.data_dir) if f.endswith('.json')])
            
            # Add 7-day summary
            stats['7_day_summary'] = self.get_large_orders_summary(7)
            
            return stats
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }


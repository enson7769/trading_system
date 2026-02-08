from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import os
import concurrent.futures
from config.config import config
from persistence.data_store import data_store
from utils.logger import logger

class LargeOrderMonitor:
    def __init__(self, 
                 threshold: Optional[Decimal] = None, 
                 data_dir: str = 'data/large_orders',
                 max_memory_orders: Optional[int] = None,
                 max_workers: int = 4):
        """初始化大额订单监控器，从配置文件加载配置"""
        # 从配置文件加载配置
        system_config = config.get_system_config()
        
        # 使用提供的值或配置值或默认值
        if threshold is None:
            threshold = Decimal(str(system_config.get('large_order_threshold', 100)))
        
        if max_memory_orders is None:
            max_memory_orders = system_config.get('max_large_orders_memory', 1000)
        
        # 验证阈值
        if threshold <= Decimal('0'):
            raise ValueError("阈值必须为正数")
        
        self.threshold = threshold
        self.data_dir = data_dir
        self.max_memory_orders = max_memory_orders
        self.max_workers = max_workers
        
        os.makedirs(self.data_dir, exist_ok=True)
        self.large_orders: List[Dict[str, Any]] = []
        self._order_index: Dict[str, List[str]] = {}  # symbol -> list of filenames
        self._build_index()
    
    def _build_index(self) -> None:
        """构建内存索引以加快查找速度"""
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
            logger.error(f"构建订单索引错误: {e}")
    
    def set_threshold(self, threshold: Decimal) -> bool:
        """动态更新大额订单阈值"""
        try:
            if threshold <= Decimal('0'):
                raise ValueError("阈值必须为正数")
            self.threshold = threshold
            logger.info(f"已更新大额订单阈值为 {threshold}")
            return True
        except Exception as e:
            logger.error(f"设置阈值错误: {e}")
            return False
    
    def check_large_order(self, order: Dict[str, Any]) -> bool:
        """检查订单是否被视为大额订单"""
        try:
            quantity = order.get('quantity')
            if quantity is None:
                return False
            
            # 处理不同类型的数量值
            if isinstance(quantity, str):
                quantity = Decimal(quantity)
            elif not isinstance(quantity, Decimal):
                quantity = Decimal(str(quantity))
            
            return quantity >= self.threshold
        except Exception as e:
            logger.error(f"检查大额订单错误: {e}")
            return False
    
    def record_large_order(self, order: Dict[str, Any]) -> bool:
        """记录大额订单，包含错误处理"""
        try:
            if not self.check_large_order(order):
                return False
            
            # 验证必需字段
            if not order.get('order_id'):
                logger.warning("大额订单缺少order_id")
            
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
            
            # 管理内存使用
            if len(self.large_orders) >= self.max_memory_orders:
                self.large_orders.pop(0)  # 移除最旧的订单
            self.large_orders.append(order_data)
            
            # 写入文件，包含错误处理
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 包含毫秒
            filename = f"large_order_{timestamp}.json"
            filepath = os.path.join(self.data_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(order_data, f, indent=2, ensure_ascii=False)
            
            # 更新索引
            symbol = order.get('symbol')
            if symbol:
                if symbol not in self._order_index:
                    self._order_index[symbol] = []
                self._order_index[symbol].append(filename)
            
            # 保存到数据存储
            try:
                db_order_data = {
                    'order_id': order.get('order_id'),
                    'account_id': order.get('account_id'),
                    'symbol': order.get('symbol'),
                    'side': order.get('side'),
                    'quantity': order.get('quantity'),
                    'price': order.get('price'),
                    'gateway_name': order.get('gateway_name')
                }
                saved = data_store.save_large_order(db_order_data)
                if saved:
                    logger.info(f"大额订单 {order.get('order_id')} 已保存到数据存储")
                else:
                    logger.error(f"保存大额订单到数据存储失败")
            except Exception as db_error:
                logger.error(f"保存大额订单到数据存储错误: {db_error}")
            
            logger.info(f"已记录大额订单: {order.get('order_id')}，数量 {order.get('quantity')} 单位")
            return True
            
        except Exception as e:
            logger.error(f"记录大额订单错误: {e}")
            return False
    
    def record_orders_batch(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量记录多个订单以提高性能"""
        results = {
            'total': len(orders),
            'large_orders': 0,
            'recorded': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            # 首先识别大额订单
            large_orders_to_record = []
            for order in orders:
                if self.check_large_order(order):
                    results['large_orders'] += 1
                    large_orders_to_record.append(order)
            
            # 并行记录大额订单
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
            logger.error(f"批量记录错误: {e}")
            results['errors'].append(str(e))
        
        return results
    
    def get_large_orders_summary(self, days: int = 7) -> Dict[str, Any]:
        """获取大额订单摘要，提高性能"""
        summary = {
            'total_large_orders': 0,
            'by_symbol': {},
            'by_side': {},
            'by_account': {},
            'total_quantity': Decimal('0'),
            'average_quantity': Decimal('0'),
            'period': f'{days} 天'
        }
        
        try:
            recent_orders = self._get_recent_orders(days)
            summary['total_large_orders'] = len(recent_orders)
            
            for order in recent_orders:
                # 交易品种分析
                symbol = order.get('symbol')
                if symbol:
                    summary['by_symbol'][symbol] = summary['by_symbol'].get(symbol, 0) + 1
                
                # 方向分析
                side = order.get('side')
                if side:
                    summary['by_side'][side] = summary['by_side'].get(side, 0) + 1
                
                # 账户分析
                account_id = order.get('account_id')
                if account_id:
                    summary['by_account'][account_id] = summary['by_account'].get(account_id, 0) + 1
                
                # 数量分析
                quantity_str = order.get('quantity', '0')
                try:
                    quantity = Decimal(quantity_str)
                    summary['total_quantity'] += quantity
                except Exception:
                    pass
            
            # 计算平均数量
            if summary['total_large_orders'] > 0:
                summary['average_quantity'] = summary['total_quantity'] / Decimal(str(summary['total_large_orders']))
        
        except Exception as e:
            logger.error(f"获取大额订单摘要错误: {e}")
            summary['error'] = str(e)
        
        return summary
    
    def _get_recent_orders(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取最近的大额订单，使用并行处理"""
        recent_orders = []
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        try:
            # 收集所有相关文件
            relevant_files = []
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.json'):
                    relevant_files.append(filename)
            
            # 并行处理文件
            def process_file(filename: str) -> Optional[Dict[str, Any]]:
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        order_data = json.load(f)
                    order_time = datetime.fromisoformat(order_data['timestamp']).timestamp()
                    if order_time >= cutoff_time:
                        return order_data
                except Exception as e:
                    logger.error(f"读取订单文件 {filename} 错误: {e}")
                return None
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                results = executor.map(process_file, relevant_files)
                for result in results:
                    if result:
                        recent_orders.append(result)
        
        except Exception as e:
            logger.error(f"获取最近订单错误: {e}")
        
        return recent_orders
    
    def get_large_orders_by_symbol(self, symbol: str, days: int = 7) -> List[Dict[str, Any]]:
        """获取特定交易品种的大额订单"""
        try:
            # 使用索引加快查找
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
            
            # 按时间戳排序（最新的在前）
            recent_orders.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return recent_orders
        
        except Exception as e:
            logger.error(f"按交易品种获取订单错误: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取大额订单的综合统计信息"""
        try:
            stats = {
                'current_threshold': str(self.threshold),
                'memory_orders_count': len(self.large_orders),
                'indexed_symbols': len(self._order_index),
                'total_files': 0,
                'last_updated': datetime.now().isoformat()
            }
            
            # 计算总文件数
            stats['total_files'] = len([f for f in os.listdir(self.data_dir) if f.endswith('.json')])
            
            # 添加7天摘要
            stats['7_day_summary'] = self.get_large_orders_summary(7)
            
            return stats
        except Exception as e:
            logger.error(f"获取统计信息错误: {e}")
            return {
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }


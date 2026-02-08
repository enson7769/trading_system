#!/usr/bin/env python3
"""
数据持久化服务
使用SQLite实现数据存储，确保系统重启后数据不丢失
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal
import os

class DataStore:
    """数据持久化存储服务"""
    
    def __init__(self, db_path: str = "data/trading_system.db"):
        """初始化数据存储
        
        Args:
            db_path: 数据库文件路径
        """
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 订单历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS order_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE,
                    instrument_symbol TEXT,
                    side TEXT,
                    type TEXT,
                    quantity TEXT,
                    price TEXT,
                    status TEXT,
                    filled_qty TEXT,
                    gateway_order_id TEXT,
                    account_id TEXT,
                    outcome TEXT,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 账户信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS account_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT UNIQUE,
                    gateway_name TEXT,
                    balances TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 策略状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 事件记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS event_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT,
                    event_data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 大额订单表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS large_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    symbol TEXT,
                    side TEXT,
                    quantity TEXT,
                    price TEXT,
                    account_id TEXT,
                    gateway_name TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def save_order(self, order: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """保存订单信息
        
        Args:
            order: 订单信息
            result: 订单执行结果
            
        Returns:
            bool: 是否保存成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO order_history 
                    (order_id, instrument_symbol, side, type, quantity, price, status, filled_qty, 
                     gateway_order_id, account_id, outcome, result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order.get('order_id'),
                    order.get('instrument', {}).get('symbol') if isinstance(order.get('instrument'), dict) else None,
                    order.get('side'),
                    order.get('type'),
                    str(order.get('quantity')),
                    str(order.get('price')) if order.get('price') else None,
                    order.get('status'),
                    str(order.get('filled_qty', 0)),
                    order.get('gateway_order_id'),
                    order.get('account_id'),
                    order.get('outcome'),
                    json.dumps(result)
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存订单失败: {e}")
            return False
    
    def get_order_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """获取订单历史
        
        Args:
            limit: 返回记录数限制
            
        Returns:
            List[Dict[str, Any]]: 订单历史列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM order_history 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                orders = []
                for row in rows:
                    order = dict(row)
                    order['result'] = json.loads(order['result']) if order['result'] else None
                    order['quantity'] = Decimal(order['quantity']) if order['quantity'] else None
                    order['price'] = Decimal(order['price']) if order['price'] else None
                    order['filled_qty'] = Decimal(order['filled_qty']) if order['filled_qty'] else None
                    orders.append(order)
                
                return orders
        except Exception as e:
            print(f"获取订单历史失败: {e}")
            return []
    
    def save_account(self, account_id: str, gateway_name: str, balances: Dict[str, Decimal]) -> bool:
        """保存账户信息
        
        Args:
            account_id: 账户ID
            gateway_name: 网关名称
            balances: 账户余额
            
        Returns:
            bool: 是否保存成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 将Decimal转换为字符串存储
                balances_str = json.dumps({k: str(v) for k, v in balances.items()})
                
                cursor.execute('''
                    INSERT OR REPLACE INTO account_info 
                    (account_id, gateway_name, balances, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (
                    account_id,
                    gateway_name,
                    balances_str,
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存账户信息失败: {e}")
            return False
    
    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """获取账户信息
        
        Args:
            account_id: 账户ID
            
        Returns:
            Optional[Dict[str, Any]]: 账户信息
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM account_info WHERE account_id = ?
                ''', (account_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                account = dict(row)
                # 将字符串转换回Decimal
                balances = json.loads(account['balances']) if account['balances'] else {}
                account['balances'] = {k: Decimal(v) for k, v in balances.items()}
                
                return account
        except Exception as e:
            print(f"获取账户信息失败: {e}")
            return None
    
    def save_strategy_state(self, key: str, value: Any) -> bool:
        """保存策略状态
        
        Args:
            key: 状态键
            value: 状态值
            
        Returns:
            bool: 是否保存成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 确保值可以被JSON序列化
                value_str = json.dumps(value, default=str)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO strategy_state 
                    (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', (
                    key,
                    value_str,
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存策略状态失败: {e}")
            return False
    
    def get_strategy_state(self, key: str) -> Optional[Any]:
        """获取策略状态
        
        Args:
            key: 状态键
            
        Returns:
            Optional[Any]: 状态值
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT value FROM strategy_state WHERE key = ?
                ''', (key,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                value = json.loads(row['value'])
                return value
        except Exception as e:
            print(f"获取策略状态失败: {e}")
            return None
    
    def save_event(self, event_name: str, event_data: Dict[str, Any]) -> bool:
        """保存事件记录
        
        Args:
            event_name: 事件名称
            event_data: 事件数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                event_data_str = json.dumps(event_data, default=str)
                
                cursor.execute('''
                    INSERT INTO event_records (event_name, event_data)
                    VALUES (?, ?)
                ''', (event_name, event_data_str))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存事件记录失败: {e}")
            return False
    
    def save_large_order(self, order_info: Dict[str, Any]) -> bool:
        """保存大额订单记录
        
        Args:
            order_info: 订单信息
            
        Returns:
            bool: 是否保存成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO large_orders 
                    (order_id, symbol, side, quantity, price, account_id, gateway_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order_info.get('order_id'),
                    order_info.get('symbol'),
                    order_info.get('side'),
                    str(order_info.get('quantity')),
                    str(order_info.get('price')),
                    order_info.get('account_id'),
                    order_info.get('gateway_name')
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存大额订单记录失败: {e}")
            return False
    
    def clear_all(self) -> bool:
        """清空所有数据
        
        Returns:
            bool: 是否清空成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 清空所有表
                tables = ['order_history', 'account_info', 'strategy_state', 'event_records', 'large_orders']
                for table in tables:
                    cursor.execute(f'DELETE FROM {table}')
                
                conn.commit()
                return True
        except Exception as e:
            print(f"清空数据失败: {e}")
            return False

# 创建全局数据存储实例
data_store = DataStore()

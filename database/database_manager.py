import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
import os
import json
from typing import Dict, Any, Optional, List, Tuple
import logging
from config.config import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """MySQL数据库操作管理器"""
    
    def __init__(self):
        """初始化数据库管理器"""
        self.config = self._load_config()
        self.connection = None
        self.cursor = None
        self.pool = None
        self._initialize_connection_pool()
    
    def _load_config(self) -> Dict[str, str]:
        """加载数据库配置"""
        # 从配置管理器加载
        db_config = config.get_database_config()
        
        return {
            'host': db_config.get('host', 'localhost'),
            'port': db_config.get('port', '3306'),
            'user': db_config.get('user', 'root'),
            'password': db_config.get('password', '123456'),
            'database': db_config.get('database', 'trading_system')
        }
    
    def _initialize_connection_pool(self):
        """初始化数据库连接池"""
        try:
            # 配置连接池
            pool_config = {
                'pool_name': 'trading_system_pool',
                'pool_size': 5,
                'pool_reset_session': True,
                'host': self.config['host'],
                'port': self.config['port'],
                'user': self.config['user'],
                'password': self.config['password'],
                'database': self.config['database']
            }
            
            # 创建连接池
            self.pool = MySQLConnectionPool(**pool_config)
            logger.info("数据库连接池初始化成功")
        except Error as e:
            logger.error(f"初始化数据库连接池错误: {e}")
            self.pool = None
    
    def connect(self) -> bool:
        """连接到数据库"""
        try:
            # 优先使用连接池
            if self.pool:
                try:
                    self.connection = self.pool.get_connection()
                    if self.connection.is_connected():
                        self.cursor = self.connection.cursor(dictionary=True)
                        logger.debug(f"从连接池获取数据库连接: {self.config['database']}")
                        return True
                except Error as e:
                    logger.error(f"从连接池获取连接错误: {e}")
            
            # 如果连接池不可用，使用传统连接方式
            self.connection = mysql.connector.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database']
            )
            
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                logger.info(f"已连接到MySQL数据库: {self.config['database']}")
                return True
        except Error as e:
            logger.error(f"连接MySQL数据库错误: {e}")
        
        return False
    
    def disconnect(self):
        """断开数据库连接"""
        try:
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.connection and self.connection.is_connected():
                # 检查是否是从连接池获取的连接
                if hasattr(self.connection, 'pool_name'):
                    # 从连接池获取的连接，返回给池
                    self.connection.close()
                    logger.debug("已将连接返回给连接池")
                else:
                    # 传统连接，直接关闭
                    self.connection.close()
                    logger.info("已断开MySQL数据库连接")
                self.connection = None
        except Error as e:
            logger.error(f"断开MySQL数据库连接错误: {e}")
    
    def initialize_database(self) -> bool:
        """初始化数据库架构"""
        try:
            # 检查连接是否建立
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return False
            
            # 读取架构文件
            schema_path = os.path.join(os.path.dirname(__file__), 'db_schema.sql')
            if not os.path.exists(schema_path):
                logger.error(f"架构文件未找到: {schema_path}")
                return False
            
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # 执行架构SQL
            # 按分号分割以处理多个语句
            statements = schema_sql.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement:
                    try:
                        self.cursor.execute(statement)
                    except Error as e:
                        # 忽略表已存在的错误
                        if "already exists" not in str(e):
                            logger.error(f"执行SQL语句错误: {e}")
                            logger.error(f"语句: {statement}")
            
            self.connection.commit()
            logger.info("数据库架构初始化成功")
            return True
        except Error as e:
            logger.error(f"初始化数据库错误: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """执行SELECT查询"""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return None
            
            self.cursor.execute(query, params or ())
            result = self.cursor.fetchall()
            return result
        except Error as e:
            logger.error(f"执行查询错误: {e}")
            logger.error(f"查询: {query}")
            logger.error(f"参数: {params}")
            return None
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """执行INSERT、UPDATE或DELETE查询"""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return 0
            
            self.cursor.execute(query, params or ())
            affected_rows = self.cursor.rowcount
            self.connection.commit()
            return affected_rows
        except Error as e:
            logger.error(f"执行更新错误: {e}")
            logger.error(f"查询: {query}")
            logger.error(f"参数: {params}")
            if self.connection:
                self.connection.rollback()
            return 0
    
    def call_procedure(self, procedure_name: str, params: Optional[Tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """调用存储过程"""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return None
            
            # 对于存储过程，需要使用不同的游标
            proc_cursor = self.connection.cursor(dictionary=True)
            proc_cursor.callproc(procedure_name, params or ())
            
            # 获取过程的结果
            result = []
            for result_set in proc_cursor.stored_results():
                result.extend(result_set.fetchall())
            
            proc_cursor.close()
            return result
        except Error as e:
            logger.error(f"调用存储过程错误: {e}")
            logger.error(f"过程: {procedure_name}")
            logger.error(f"参数: {params}")
            return None
    
    def get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return 0
            
            self.cursor.execute("SELECT LAST_INSERT_ID() as id")
            result = self.cursor.fetchone()
            return result['id'] if result else 0
        except Error as e:
            logger.error(f"获取最后插入ID错误: {e}")
            return 0
    
    def execute_batch(self, query: str, params_list: List[Tuple]) -> int:
        """批量执行INSERT、UPDATE或DELETE查询
        
        Args:
            query: SQL查询语句
            params_list: 参数列表
            
        Returns:
            int: 影响的行数
        """
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return 0
            
            # 关闭自动提交
            self.connection.autocommit = False
            
            # 使用executemany批量执行
            if params_list:
                self.cursor.executemany(query, params_list)
                affected_rows = self.cursor.rowcount
            else:
                affected_rows = 0
            
            # 批量提交
            self.connection.commit()
            
            # 恢复自动提交
            self.connection.autocommit = True
            
            logger.debug(f"批量执行完成，影响行数: {affected_rows}")
            return affected_rows
        except Error as e:
            logger.error(f"批量执行错误: {e}")
            logger.error(f"查询: {query}")
            if self.connection:
                self.connection.rollback()
                # 恢复自动提交
                self.connection.autocommit = True
            return 0
    
    def is_connected(self) -> bool:
        """检查数据库连接是否活跃"""
        try:
            return self.connection and self.connection.is_connected()
        except:
            return False

# 创建单例实例
db_manager = DatabaseManager()

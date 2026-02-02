import mysql.connector
from mysql.connector import Error
import os
import json
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database manager for MySQL operations"""
    
    def __init__(self):
        """Initialize database manager"""
        self.config = self._load_config()
        self.connection = None
        self.cursor = None
    
    def _load_config(self) -> Dict[str, str]:
        """Load database configuration"""
        # Default configuration
        config = {
            'host': 'localhost',
            'port': '3306',
            'user': 'root',
            'password': '',
            'database': 'trading_system'
        }
        
        # Override with environment variables if present
        env_config = {
            'host': os.environ.get('DB_HOST'),
            'port': os.environ.get('DB_PORT'),
            'user': os.environ.get('DB_USER'),
            'password': os.environ.get('DB_PASSWORD'),
            'database': os.environ.get('DB_NAME')
        }
        
        for key, value in env_config.items():
            if value:
                config[key] = value
        
        return config
    
    def connect(self) -> bool:
        """Connect to the database"""
        try:
            self.connection = mysql.connector.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database']
            )
            
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                logger.info(f"Connected to MySQL database: {self.config['database']}")
                return True
        except Error as e:
            logger.error(f"Error connecting to MySQL database: {e}")
        
        return False
    
    def disconnect(self):
        """Disconnect from the database"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection and self.connection.is_connected():
                self.connection.close()
                logger.info("Disconnected from MySQL database")
        except Error as e:
            logger.error(f"Error disconnecting from MySQL database: {e}")
    
    def initialize_database(self) -> bool:
        """Initialize database schema"""
        try:
            # Check if connection is established
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return False
            
            # Read schema file
            schema_path = os.path.join(os.path.dirname(__file__), 'db_schema.sql')
            if not os.path.exists(schema_path):
                logger.error(f"Schema file not found: {schema_path}")
                return False
            
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Execute schema SQL
            # Split by semicolon to handle multiple statements
            statements = schema_sql.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement:
                    try:
                        self.cursor.execute(statement)
                    except Error as e:
                        # Ignore duplicate table errors
                        if "already exists" not in str(e):
                            logger.error(f"Error executing SQL statement: {e}")
                            logger.error(f"Statement: {statement}")
            
            self.connection.commit()
            logger.info("Database schema initialized successfully")
            return True
        except Error as e:
            logger.error(f"Error initializing database: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """Execute a SELECT query"""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return None
            
            self.cursor.execute(query, params or ())
            result = self.cursor.fetchall()
            return result
        except Error as e:
            logger.error(f"Error executing query: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            return None
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """Execute an INSERT, UPDATE, or DELETE query"""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return 0
            
            self.cursor.execute(query, params or ())
            affected_rows = self.cursor.rowcount
            self.connection.commit()
            return affected_rows
        except Error as e:
            logger.error(f"Error executing update: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            if self.connection:
                self.connection.rollback()
            return 0
    
    def call_procedure(self, procedure_name: str, params: Optional[Tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """Call a stored procedure"""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return None
            
            # For stored procedures, we need to use a different cursor
            proc_cursor = self.connection.cursor(dictionary=True)
            proc_cursor.callproc(procedure_name, params or ())
            
            # Get results from the procedure
            result = []
            for result_set in proc_cursor.stored_results():
                result.extend(result_set.fetchall())
            
            proc_cursor.close()
            return result
        except Error as e:
            logger.error(f"Error calling stored procedure: {e}")
            logger.error(f"Procedure: {procedure_name}")
            logger.error(f"Params: {params}")
            return None
    
    def get_last_insert_id(self) -> int:
        """Get the last inserted ID"""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self.connect():
                    return 0
            
            self.cursor.execute("SELECT LAST_INSERT_ID() as id")
            result = self.cursor.fetchone()
            return result['id'] if result else 0
        except Error as e:
            logger.error(f"Error getting last insert ID: {e}")
            return 0
    
    def is_connected(self) -> bool:
        """Check if the database connection is active"""
        try:
            return self.connection and self.connection.is_connected()
        except:
            return False

# Create a singleton instance
db_manager = DatabaseManager()

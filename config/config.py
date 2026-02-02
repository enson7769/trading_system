import os
from typing import Dict, Any
import yaml

class Config:
    """系统配置管理器"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """从文件加载配置"""
        # 默认配置
        default_config = {
                    # 数据库配置
                    'database': {
                        'host': os.environ.get('DB_HOST', 'localhost'),
                        'port': os.environ.get('DB_PORT', '3306'),
                        'user': os.environ.get('DB_USER', 'root'),
                        'password': os.environ.get('DB_PASSWORD', ''),
                        'database': os.environ.get('DB_NAME', 'trading_system')
                    },
                    # 系统配置
                    'system': {
                        'max_order_history': 10000,
                        'max_large_orders_memory': 1000,
                        'large_order_threshold': 100,
                        'default_refresh_interval': 5,
                        'default_page_size': 100
                    },
                    # 网关配置
                    'gateways': {
                        'polymarket': {
                            'rpc_url': 'https://polygon-rpc.com/',
                            'mock': True,
                            'exchange_address': '0x435AB6645531D3f5391E8B8DA9c0F7b64e6C7e11',
                            'usdc_address': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
                        }
                    },
                    # 账户配置
                    'accounts': {
                        'main_account': {
                            'gateway': 'polymarket',
                            'initial_balances': {
                                'USDC': 10000
                            }
                        }
                    },
                    # 流动性配置
                    'liquidity': {
                        'max_history_per_symbol': 10000,
                        'min_data_points': 10,
                        'recent_data_days': 7,
                        'min_recent_data': 5
                    },
                    # 事件配置
                    'events': {
                        'data_dir': 'data/events',
                        'max_workers': 4,
                        'batch_size': 10,
                        'important_events': [
                            'powell_speech',
                            'unemployment_rate',
                            'cpi',
                            'ppi',
                            'fomc_meeting',
                            'gdp',
                            'retail_sales',
                            'nonfarm_payrolls'
                        ]
                    },
                    # 策略配置
                    'strategy': {
                        'probability': {
                            'min_total_probability': 90,
                            'safe_total_probability': 97
                        }
                    }
                }
        
        # 从配置文件加载（如果存在）
        file_config = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
            except Exception as e:
                print(f"加载配置文件错误: {e}")
                # 如果文件加载失败，使用空配置
        
        # 从文件配置创建基础配置
        base_config = {}
        self._merge_config(base_config, file_config)
        
        # 将默认配置（含环境变量）合并到基础配置
        # 这样环境变量会覆盖文件配置，具有更高优先级
        self._merge_config(base_config, default_config)
        
        return base_config
    
    def _merge_config(self, default: Dict[str, Any], override: Dict[str, Any]) -> None:
        """将覆盖配置合并到默认配置中"""
        for key, value in override.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                self._merge_config(default[key], value)
            else:
                default[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """通过点分隔的键获取配置值"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """通过点分隔的键设置配置值"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self) -> bool:
        """保存配置到文件"""
        try:
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, indent=2, allow_unicode=True, default_flow_style=False)
            return True
        except Exception as e:
            print(f"保存配置文件错误: {e}")
            return False
    
    def get_database_config(self) -> Dict[str, str]:
        """获取数据库配置"""
        return self.config.get('database', {})
    
    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return self.config.get('system', {})
    
    def get_gateway_config(self, gateway_name: str) -> Dict[str, Any]:
        """获取网关配置"""
        return self.config.get('gateways', {}).get(gateway_name, {})
    
    def get_account_config(self, account_name: str) -> Dict[str, Any]:
        """获取账户配置"""
        return self.config.get('accounts', {}).get(account_name, {})
    
    def get_liquidity_config(self) -> Dict[str, Any]:
        """获取流动性配置"""
        return self.config.get('liquidity', {})
    
    def get_events_config(self) -> Dict[str, Any]:
        """获取事件配置"""
        return self.config.get('events', {})
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """获取策略配置"""
        return self.config.get('strategy', {}).get(strategy_name, {})

# 创建单例实例
config = Config()

import json
import time
from web3 import Web3
from eth_account import Account
import requests
from core.models import Order, Instrument
from gateways.base import BaseGateway
from utils.logger import logger
from security.credential_manager import CredentialManager
from config.config import config

class PolymarketGateway(BaseGateway):
    """Polymarket交易网关"""
    
    def __init__(self, rpc_url: str, credential_manager: CredentialManager, mock: bool = None):
        """初始化Polymarket网关
        
        Args:
            rpc_url: RPC节点URL
            credential_manager: 凭证管理器
            mock: 是否启用模拟模式
        """
        super().__init__("polymarket")
        # 加载配置
        gateway_config = config.get_gateway_config('polymarket')
        
        # 使用提供的值或配置值或默认值
        if mock is None:
            mock = gateway_config.get('mock', True)
        
        self.rpc_url = rpc_url
        self.cred_mgr = credential_manager
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.private_key = None
        self.address = None
        self.no_input = False
        self.mock = mock
        # 从配置加载合约地址
        self.exchange_address = gateway_config.get('exchange_address', "0x435AB6645531D3f5391E8B8DA9c0F7b64e6C7e11")
        self.usdc_address = gateway_config.get('usdc_address', "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
        
        # 从配置加载API端点
        self.gamma_api_url = gateway_config.get('gamma_api_url', "https://gamma-api.polymarket.com")
        self.clob_api_url = gateway_config.get('clob_api_url', "https://clob.polymarket.com")
        self.data_api_url = gateway_config.get('data_api_url', "https://data-api.polymarket.com")
        self.websocket_url = gateway_config.get('websocket_url', "wss://ws-subscriptions-clob.polymarket.com")
        
        # 从配置加载账户信息
        self.address = gateway_config.get('address', None)
        self.api_key = gateway_config.get('api_key', None)
        
        # 从配置加载API配置
        self.api_timeout = gateway_config.get('api_timeout', 30)
        self.api_retries = gateway_config.get('api_retries', 3)

    def connect(self):
        """连接到Polymarket"""
        if self.mock:
            # 模拟模式：跳过实际连接，使用测试数据
            self.private_key = "0x" + "a" * 64  # 模拟私钥
            # 使用配置文件中的地址或默认模拟地址
            if self.address:
                logger.info(f"[MOCK] 已连接Polymarket钱包: {self.address[:6]}...{self.address[-4:]}")
            else:
                self.address = "0xMockAddress12345678901234567890123456789012"
                logger.info(f"[MOCK] 已连接Polymarket钱包: {self.address[:6]}...{self.address[-4:]}")
            return

        if not self.w3.is_connected():
            raise ConnectionError("连接RPC失败")

        # 如果配置文件中有地址，直接使用
        if self.address:
            logger.info(f"已连接Polymarket钱包: {self.address[:6]}...{self.address[-4:]}")
            return

        # 否则，从私钥生成地址
        self.private_key = self.cred_mgr.get_secret(
            key="polymarket_private_key",
            prompt="输入Polymarket钱包私钥 (隐藏): ",
            env_var="POLYMARKET_PRIVATE_KEY",
            no_input=self.no_input
        )
        
        # 验证私钥格式
        if not self._validate_private_key(self.private_key):
            raise ValueError("无效的私钥格式。请提供有效的64字符十六进制字符串。")
        
        account = Account.from_key(self.private_key)
        self.address = account.address
        logger.info(f"已连接Polymarket钱包: {self.address[:6]}...{self.address[-4:]}")
    
    def _validate_private_key(self, private_key: str) -> bool:
        """验证私钥是否为有效的十六进制字符串"""
        # 移除开头的0x前缀（如果有）
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        
        # 检查长度（64个十六进制字符 = 32字节）
        if len(private_key) != 64:
            return False
        
        # 检查所有字符是否为十六进制
        try:
            int(private_key, 16)
            return True
        except ValueError:
            return False

    def send_order(self, order: Order) -> str:
        """发送订单到Polymarket"""
        if self.mock:
            # 模拟交易
            tx_hash = self._simulate_trade(order)
            logger.info(f"[MOCK] 已模拟Polymarket订单: {tx_hash}")
            return tx_hash
        
        # 实际交易实现（待完成）
        # 这里将使用CLOB API发送订单
        logger.info(f"发送订单到Polymarket: {order.order_id}")
        # 临时返回模拟交易哈希
        return self._simulate_trade(order)

    def _simulate_trade(self, order) -> str:
        """模拟交易，返回假的交易哈希"""
        time.sleep(0.1)  # 模拟网络延迟
        return "0x" + "a1b2c3d4e5f6" * 5  # 假的交易哈希
    
    # Gamma API methods
    def get_events(self) -> list:
        """获取所有事件
        
        Returns:
            list: 事件列表
        """
        if self.mock:
            # 模拟数据
            return [
                {
                    "id": "event1",
                    "title": "Fed Meeting Outcome",
                    "description": "Federal Reserve meeting outcome",
                    "categories": ["finance", "us"]
                },
                {
                    "id": "event2",
                    "title": "CPI Data Release",
                    "description": "Consumer Price Index data release",
                    "categories": ["finance", "us", "inflation"]
                }
            ]
        
        try:
            url = f"{self.gamma_api_url}/events"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取事件失败: {e}")
            return []
    
    def get_markets(self, event_id: str = None) -> list:
        """获取市场列表
        
        Args:
            event_id: 事件ID（可选）
            
        Returns:
            list: 市场列表
        """
        if self.mock:
            # 模拟数据
            return [
                {
                    "id": "market1",
                    "event_id": "event1",
                    "question": "Will the Fed raise rates?",
                    "outcomes": ["Yes", "No"],
                    "status": "active"
                },
                {
                    "id": "market2",
                    "event_id": "event2",
                    "question": "Will CPI be above 3%?",
                    "outcomes": ["Yes", "No"],
                    "status": "active"
                }
            ]
        
        try:
            if event_id:
                url = f"{self.gamma_api_url}/markets?event_id={event_id}"
            else:
                url = f"{self.gamma_api_url}/markets"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取市场失败: {e}")
            return []
    
    def get_market(self, market_id: str) -> dict:
        """获取单个市场详情
        
        Args:
            market_id: 市场ID
            
        Returns:
            dict: 市场详情
        """
        if self.mock:
            # 模拟数据
            return {
                "id": market_id,
                "event_id": "event1",
                "question": "Will the Fed raise rates?",
                "outcomes": ["Yes", "No"],
                "status": "active",
                "created_at": "2026-01-01T00:00:00Z",
                "resolve_at": "2026-02-01T00:00:00Z"
            }
        
        try:
            url = f"{self.gamma_api_url}/markets/{market_id}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取市场详情失败: {e}")
            return {}
    
    def get_categories(self) -> list:
        """获取所有类别
        
        Returns:
            list: 类别列表
        """
        if self.mock:
            # 模拟数据
            return [
                {"id": "finance", "name": "Finance"},
                {"id": "us", "name": "US"},
                {"id": "inflation", "name": "Inflation"},
                {"id": "politics", "name": "Politics"}
            ]
        
        try:
            url = f"{self.gamma_api_url}/categories"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取类别失败: {e}")
            return []
    
    # CLOB API methods
    def get_order_book(self, market_id: str, depth: int = 10) -> dict:
        """获取订单簿
        
        Args:
            market_id: 市场ID
            depth: 订单簿深度
            
        Returns:
            dict: 订单簿数据
        """
        if self.mock:
            # 模拟数据
            return {
                "market_id": market_id,
                "asks": [
                    {"price": "0.65", "size": "100"},
                    {"price": "0.66", "size": "200"},
                    {"price": "0.67", "size": "150"}
                ],
                "bids": [
                    {"price": "0.64", "size": "120"},
                    {"price": "0.63", "size": "180"},
                    {"price": "0.62", "size": "100"}
                ],
                "timestamp": time.time()
            }
        
        try:
            url = f"{self.clob_api_url}/orderbook/{market_id}?depth={depth}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取订单簿失败: {e}")
            return {"asks": [], "bids": []}
    
    def get_market_price(self, market_id: str) -> dict:
        """获取市场价格
        
        Args:
            market_id: 市场ID
            
        Returns:
            dict: 价格数据
        """
        if self.mock:
            # 模拟数据
            return {
                "market_id": market_id,
                "last_price": "0.645",
                "bid": "0.64",
                "ask": "0.65",
                "volume": "10000"
            }
        
        try:
            url = f"{self.clob_api_url}/price/{market_id}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取市场价格失败: {e}")
            return {"last_price": "0", "bid": "0", "ask": "0"}
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 是否取消成功
        """
        if self.mock:
            # 模拟取消
            logger.info(f"[MOCK] 取消订单: {order_id}")
            return True
        
        try:
            url = f"{self.clob_api_url}/order/{order_id}/cancel"
            response = requests.post(url)
            response.raise_for_status()
            logger.info(f"取消订单成功: {order_id}")
            return True
        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> dict:
        """获取订单状态
        
        Args:
            order_id: 订单ID
            
        Returns:
            dict: 订单状态
        """
        if self.mock:
            # 模拟数据
            return {
                "order_id": order_id,
                "status": "filled",
                "price": "0.645",
                "size": "100",
                "filled_size": "100",
                "timestamp": time.time()
            }
        
        try:
            url = f"{self.clob_api_url}/order/{order_id}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取订单状态失败: {e}")
            return {"status": "unknown"}
    
    # Data API methods
    def get_positions(self, address: str = None) -> list:
        """获取用户持仓
        
        Args:
            address: 用户钱包地址（可选）
            
        Returns:
            list: 持仓列表
        """
        if self.mock:
            # 模拟数据
            return [
                {
                    "market_id": "market1",
                    "outcome": "Yes",
                    "size": "100",
                    "avg_price": "0.65",
                    "current_price": "0.645",
                    "pnl": "-0.5"
                },
                {
                    "market_id": "market2",
                    "outcome": "No",
                    "size": "200",
                    "avg_price": "0.45",
                    "current_price": "0.46",
                    "pnl": "2.0"
                }
            ]
        
        try:
            if address:
                url = f"{self.data_api_url}/positions/{address}"
            else:
                url = f"{self.data_api_url}/positions/{self.address}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []
    
    def get_trade_history(self, address: str = None, limit: int = 50) -> list:
        """获取交易历史
        
        Args:
            address: 用户钱包地址（可选）
            limit: 交易数量限制
            
        Returns:
            list: 交易历史列表
        """
        if self.mock:
            # 模拟数据
            return [
                {
                    "id": "trade1",
                    "market_id": "market1",
                    "outcome": "Yes",
                    "side": "buy",
                    "price": "0.65",
                    "size": "100",
                    "timestamp": time.time() - 3600
                },
                {
                    "id": "trade2",
                    "market_id": "market2",
                    "outcome": "No",
                    "side": "sell",
                    "price": "0.46",
                    "size": "50",
                    "timestamp": time.time() - 1800
                }
            ]
        
        try:
            if address:
                url = f"{self.data_api_url}/trades/{address}?limit={limit}"
            else:
                url = f"{self.data_api_url}/trades/{self.address}?limit={limit}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取交易历史失败: {e}")
            return []
    
    def get_portfolio(self, address: str = None) -> dict:
        """获取投资组合数据
        
        Args:
            address: 用户钱包地址（可选）
            
        Returns:
            dict: 投资组合数据
        """
        if self.mock:
            # 模拟数据
            return {
                "total_value": "230.0",
                "total_pnl": "1.5",
                "positions": [
                    {
                        "market_id": "market1",
                        "outcome": "Yes",
                        "value": "64.5",
                        "pnl": "-0.5"
                    },
                    {
                        "market_id": "market2",
                        "outcome": "No",
                        "value": "92.0",
                        "pnl": "2.0"
                    }
                ],
                "stats": {
                    "total_trades": 10,
                    "win_rate": 0.6,
                    "avg_win": 2.5,
                    "avg_loss": 1.2
                }
            }
        
        try:
            if address:
                url = f"{self.data_api_url}/portfolio/{address}"
            else:
                url = f"{self.data_api_url}/portfolio/{self.address}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取投资组合数据失败: {e}")
            return {"total_value": "0", "total_pnl": "0", "positions": []}
    
    def get_market_trades(self, market_id: str, limit: int = 50) -> list:
        """获取市场交易历史
        
        Args:
            market_id: 市场ID
            limit: 交易数量限制
            
        Returns:
            list: 市场交易历史列表
        """
        if self.mock:
            # 模拟数据
            return [
                {
                    "id": "trade1",
                    "outcome": "Yes",
                    "side": "buy",
                    "price": "0.65",
                    "size": "100",
                    "timestamp": time.time() - 3600
                },
                {
                    "id": "trade2",
                    "outcome": "Yes",
                    "side": "sell",
                    "price": "0.64",
                    "size": "50",
                    "timestamp": time.time() - 1800
                }
            ]
        
        try:
            url = f"{self.data_api_url}/market/{market_id}/trades?limit={limit}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取市场交易历史失败: {e}")
            return []
    
    # WebSocket methods
    async def connect_websocket(self):
        """连接WebSocket"""
        if self.mock:
            logger.info("[MOCK] 已连接WebSocket")
            return
        
        try:
            import websockets
            
            async with websockets.connect(self.websocket_url) as websocket:
                logger.info("已连接WebSocket")
                
                # 发送初始订阅消息
                subscribe_message = {
                    "type": "USER",
                    "markets": [],  # 订阅所有市场
                    "auth": {
                        "address": self.address
                        # 实际使用时可能需要添加签名
                    }
                }
                await websocket.send(json.dumps(subscribe_message))
                logger.info("已发送订阅消息")
                
                # 接收消息
                async for message in websocket:
                    data = json.loads(message)
                    await self._handle_websocket_message(data)
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
    
    async def _handle_websocket_message(self, data: dict):
        """处理WebSocket消息
        
        Args:
            data: WebSocket消息数据
        """
        try:
            message_type = data.get('type')
            
            if message_type == 'trade':
                # 处理交易消息
                await self._handle_trade_message(data)
            elif message_type == 'orderbook':
                # 处理订单簿消息
                await self._handle_orderbook_message(data)
            elif message_type == 'order':
                # 处理订单消息
                await self._handle_order_message(data)
            elif message_type == 'position':
                # 处理持仓消息
                await self._handle_position_message(data)
            elif message_type == 'error':
                # 处理错误消息
                logger.error(f"WebSocket错误: {data.get('error')}")
            else:
                # 处理其他消息
                logger.info(f"收到WebSocket消息: {message_type}")
        except Exception as e:
            logger.error(f"处理WebSocket消息失败: {e}")
    
    async def _handle_trade_message(self, data: dict):
        """处理交易消息
        
        Args:
            data: 交易消息数据
        """
        logger.info(f"收到交易消息: {data}")
        # 这里可以触发交易事件回调
    
    async def _handle_orderbook_message(self, data: dict):
        """处理订单簿消息
        
        Args:
            data: 订单簿消息数据
        """
        logger.info(f"收到订单簿消息: {data}")
        # 这里可以触发订单簿更新回调
    
    async def _handle_order_message(self, data: dict):
        """处理订单消息
        
        Args:
            data: 订单消息数据
        """
        logger.info(f"收到订单消息: {data}")
        # 这里可以触发订单状态更新回调
    
    async def _handle_position_message(self, data: dict):
        """处理持仓消息
        
        Args:
            data: 持仓消息数据
        """
        logger.info(f"收到持仓消息: {data}")
        # 这里可以触发持仓更新回调
    
    def subscribe_to_market(self, market_id: str):
        """订阅市场数据
        
        Args:
            market_id: 市场ID
        """
        if self.mock:
            logger.info(f"[MOCK] 已订阅市场: {market_id}")
            return
        
        # 实际实现（待完成）
        logger.info(f"订阅市场: {market_id}")
    
    def unsubscribe_from_market(self, market_id: str):
        """取消订阅市场数据
        
        Args:
            market_id: 市场ID
        """
        if self.mock:
            logger.info(f"[MOCK] 已取消订阅市场: {market_id}")
            return
        
        # 实际实现（待完成）
        logger.info(f"取消订阅市场: {market_id}")
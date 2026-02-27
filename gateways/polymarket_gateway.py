import json
import time
from web3 import Web3
from eth_account import Account
import requests
from core.models import Order, Instrument
from gateways.base import BaseGateway
from utils.logger import logger
from utils.retry import retry
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
            mock = gateway_config.get('mock', False)
        
        self.rpc_url = rpc_url
        self.cred_mgr = credential_manager
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.private_key = None
        self.address = None
        self.no_input = False
        self.mock = mock
        # 从配置加载合约地址
        self.exchange_address = gateway_config.get('exchange_address')
        self.usdc_address = gateway_config.get('usdc_address')
        
        # 从配置加载API端点
        self.gamma_api_url = gateway_config.get('gamma_api_url')
        self.clob_api_url = gateway_config.get('clob_api_url')
        self.data_api_url = gateway_config.get('data_api_url')
        self.websocket_url = gateway_config.get('websocket_url')
        self.withdraw_api_url = gateway_config.get('withdraw_api_url', self.clob_api_url)  # 默认为clob_api_url
        
        # 从配置加载账户信息
        self.address = gateway_config.get('address')
        self.api_key = gateway_config.get('api_key')
        
        # 从配置加载API配置
        self.api_timeout = gateway_config.get('api_timeout')
        self.api_retries = gateway_config.get('api_retries')

    def _check_geoblock(self):
        """检查地区限制"""
        try:
            import requests
            url = "https://polymarket.com/api/geoblock"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                geoblock_data = response.json()
                if geoblock_data.get('blocked'):
                    country = geoblock_data.get('country', 'Unknown')
                    ip = geoblock_data.get('ip', 'Unknown')
                    error_message = f"地区限制：您的IP地址 ({ip}) 来自 {country}，无法访问Polymarket。Polymarket仅对特定国家/地区开放。"
                    logger.error(error_message)
                    raise ConnectionError(error_message)
                else:
                    logger.info("地区限制检查通过")
            else:
                logger.warning(f"地区限制检查失败，状态码: {response.status_code}")
        except ConnectionError:
            # 重新抛出地区限制错误
            raise
        except Exception as e:
            logger.warning(f"地区限制检查异常: {e}")

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

        # 检查地区限制
        self._check_geoblock()

        # 检查RPC连接
        max_retries = 3
        retry_count = 0
        
        # 打印当前RPC节点信息
        logger.info(f"当前RPC节点: {self.rpc_url}")
        
        # 测试网络连接
        import requests
        try:
            response = requests.get(self.rpc_url, timeout=5)
            logger.info(f"RPC节点网络连接测试: 状态码 {response.status_code}")
        except Exception as e:
            logger.warning(f"RPC节点网络连接测试失败: {e}")

        while retry_count < max_retries:
            try:
                # 打印详细的连接状态
                logger.debug(f"尝试连接RPC节点: {self.rpc_url}")
                
                if self.w3.is_connected():
                    logger.info("RPC连接成功")
                    # 打印链ID和区块号
                    try:
                        chain_id = self.w3.eth.chain_id
                        block_number = self.w3.eth.block_number
                        logger.info(f"链ID: {chain_id}, 当前区块号: {block_number}")
                    except Exception as e:
                        logger.warning(f"获取链信息失败: {e}")
                    break
                else:
                    logger.warning(f"RPC连接失败，正在尝试重新连接... (尝试 {retry_count + 1}/{max_retries})")
                    # 尝试重新创建HTTPProvider
                    self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                    retry_count += 1
                    time.sleep(2)  # 等待2秒后重试
            except Exception as e:
                logger.warning(f"RPC连接异常: {e}，正在尝试重新连接... (尝试 {retry_count + 1}/{max_retries})")
                # 尝试重新创建HTTPProvider
                self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                retry_count += 1
                time.sleep(2)  # 等待2秒后重试

        if not self.w3.is_connected():
            # 尝试使用备用RPC节点
            backup_rpc_urls = [
                "https://rpc.ankr.com/polygon",
                "https://polygon-bor.publicnode.com",
                "https://rpc-mainnet.matic.network",
                "https://polygon-rpc.com",
                "https://rpc.quicknode.com/polygon"
            ]
            
            for backup_rpc in backup_rpc_urls:
                # 跳过与当前RPC相同的节点
                if backup_rpc == self.rpc_url:
                    continue
                    
                try:
                    logger.info(f"尝试使用备用RPC节点: {backup_rpc}")
                    # 测试网络连接
                    response = requests.get(backup_rpc, timeout=5)
                    logger.info(f"备用RPC节点网络连接测试: 状态码 {response.status_code}")
                    
                    self.w3 = Web3(Web3.HTTPProvider(backup_rpc))
                    if self.w3.is_connected():
                        logger.info(f"备用RPC节点连接成功: {backup_rpc}")
                        # 打印链ID和区块号
                        try:
                            chain_id = self.w3.eth.chain_id
                            block_number = self.w3.eth.block_number
                            logger.info(f"链ID: {chain_id}, 当前区块号: {block_number}")
                        except Exception as e:
                            logger.warning(f"获取链信息失败: {e}")
                        # 更新当前RPC URL
                        self.rpc_url = backup_rpc
                        break
                except Exception as e:
                    logger.warning(f"备用RPC节点连接失败: {backup_rpc}, 错误: {e}")

        if not self.w3.is_connected():
            # 最后尝试使用公共RPC节点
            public_rpc = "https://polygon.llamarpc.com"
            try:
                logger.info(f"尝试使用公共RPC节点: {public_rpc}")
                self.w3 = Web3(Web3.HTTPProvider(public_rpc))
                if self.w3.is_connected():
                    logger.info(f"公共RPC节点连接成功: {public_rpc}")
                    self.rpc_url = public_rpc
                else:
                    raise ConnectionError("所有RPC节点连接失败")
            except Exception as e:
                logger.error(f"公共RPC节点连接失败: {e}")
                raise ConnectionError("连接RPC失败，请检查网络连接或RPC节点URL是否正确")

        # 如果配置文件中有地址，直接使用
        if self.address and self.address != "YOUR_POLYMARKET_ADDRESS":
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

    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(Exception,),
        log_func=logger.warning
    )
    def send_order(self, order: Order) -> str:
        """发送订单到Polymarket"""
        if self.mock:
            # 模拟交易
            tx_hash = self._simulate_trade(order)
            logger.info(f"[MOCK] 已模拟Polymarket订单: {tx_hash}, 市场: {order.instrument.symbol}, 结果选项: {order.outcome}")
            return tx_hash
        
        # 实际交易实现（待完成）
        # 这里将使用CLOB API发送订单
        logger.info(f"发送订单到Polymarket: {order.order_id}, 市场: {order.instrument.symbol}, 结果选项: {order.outcome}")
        # 临时返回模拟交易哈希
        return self._simulate_trade(order)

    def _simulate_trade(self, order) -> str:
        """模拟交易，返回假的交易哈希"""
        time.sleep(0.1)  # 模拟网络延迟
        return "0x" + "a1b2c3d4e5f6" * 5  # 假的交易哈希
    
    # Gamma API methods
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(requests.RequestException,),
        log_func=logger.warning
    )
    def get_events(self) -> list:
        """获取所有事件
        
        Returns:
            list: 事件列表
        """
        if self.mock:
            # 模拟Polymarket真实API返回数据
            return [
                {
                    "id": "0x4e3a3754419731981c474b4a7b68c6c7d3a2e1f0",
                    "title": "2026 U.S. Presidential Election",
                    "description": "Who will win the 2026 U.S. presidential election?",
                    "categories": ["politics", "us", "election"],
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-02-05T12:00:00Z",
                    "image_url": "https://polymarket.com/images/events/2026-election.jpg",
                    "cover_image_url": "https://polymarket.com/images/events/2026-election-cover.jpg",
                    "featured": True,
                    "resolved_at": null
                },
                {
                    "id": "0x5b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c",
                    "title": "Federal Reserve Interest Rate Decision",
                    "description": "Will the Federal Reserve raise interest rates at the March 2026 meeting?",
                    "categories": ["finance", "us", "fed", "interest-rates"],
                    "status": "active",
                    "created_at": "2026-02-01T00:00:00Z",
                    "updated_at": "2026-02-05T10:00:00Z",
                    "image_url": "https://polymarket.com/images/events/fed-meeting.jpg",
                    "cover_image_url": "https://polymarket.com/images/events/fed-meeting-cover.jpg",
                    "featured": True,
                    "resolved_at": null
                },
                {
                    "id": "0x6c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d",
                    "title": "Bitcoin Price Prediction",
                    "description": "Will Bitcoin price exceed $100,000 by the end of 2026?",
                    "categories": ["crypto", "bitcoin", "price-prediction"],
                    "status": "active",
                    "created_at": "2026-01-15T00:00:00Z",
                    "updated_at": "2026-02-05T09:00:00Z",
                    "image_url": "https://polymarket.com/images/events/bitcoin-price.jpg",
                    "cover_image_url": "https://polymarket.com/images/events/bitcoin-price-cover.jpg",
                    "featured": false,
                    "resolved_at": null
                },
                {
                    "id": "0x7d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e",
                    "title": "U.S. Inflation Rate",
                    "description": "Will the U.S. inflation rate be above 3% in Q1 2026?",
                    "categories": ["finance", "us", "inflation"],
                    "status": "active",
                    "created_at": "2026-01-20T00:00:00Z",
                    "updated_at": "2026-02-05T08:00:00Z",
                    "image_url": "https://polymarket.com/images/events/inflation.jpg",
                    "cover_image_url": "https://polymarket.com/images/events/inflation-cover.jpg",
                    "featured": false,
                    "resolved_at": null
                }
            ]
        
        url = f"{self.gamma_api_url}/events"
        response = requests.get(url, timeout=self.api_timeout or 10)
        response.raise_for_status()
        return response.json()
    
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(requests.RequestException,),
        log_func=logger.warning
    )
    def get_markets(self, event_id: str = None, slug: str = None, tag: str = None, active: bool = True, closed: bool = False, limit: int = 100) -> list:
        """获取市场列表
        
        Args:
            event_id: 事件ID（可选）
            slug: 市场slug（可选）
            tag: 标签（可选）
            active: 是否活跃（默认true）
            closed: 是否已关闭（默认false）
            limit: 返回数量限制（默认100）
            
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
                    "status": "active",
                    "slug": "fed-rates",
                    "clobTokenIds": ["123456...", "789012..."]
                },
                {
                    "id": "market2",
                    "event_id": "event2",
                    "question": "Will CPI be above 3%?",
                    "outcomes": ["Yes", "No"],
                    "status": "active",
                    "slug": "cpi-prediction",
                    "clobTokenIds": ["234567...", "890123..."]
                }
            ]
        
        # 构建查询参数
        params = {
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "limit": str(limit)
        }
        
        if event_id:
            params["event_id"] = event_id
        
        if slug:
            params["slug"] = slug
        
        if tag:
            params["tag"] = tag
        
        url = f"{self.gamma_api_url}/markets"
        response = requests.get(url, params=params, timeout=self.api_timeout or 10)
        response.raise_for_status()
        return response.json()
    
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(requests.RequestException,),
        log_func=logger.warning
    )
    def get_markets_by_slug(self, slug: str, active: bool = True, closed: bool = False, limit: int = 100) -> list:
        """按Slug查询市场
        
        Args:
            slug: 市场slug
            active: 是否活跃（默认true）
            closed: 是否已关闭（默认false）
            limit: 返回数量限制（默认100）
            
        Returns:
            list: 市场列表
        """
        return self.get_markets(slug=slug, active=active, closed=closed, limit=limit)
    
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(requests.RequestException,),
        log_func=logger.warning
    )
    def get_markets_by_tag(self, tag: str, active: bool = True, closed: bool = False, limit: int = 100) -> list:
        """按标签查询市场
        
        Args:
            tag: 标签
            active: 是否活跃（默认true）
            closed: 是否已关闭（默认false）
            limit: 返回数量限制（默认100）
            
        Returns:
            list: 市场列表
        """
        return self.get_markets(tag=tag, active=active, closed=closed, limit=limit)
    
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(requests.RequestException,),
        log_func=logger.warning
    )
    def get_markets_by_event(self, event_id: str, active: bool = True, closed: bool = False, limit: int = 100) -> list:
        """通过事件接口获取市场数据
        
        Args:
            event_id: 事件ID
            active: 是否活跃（默认true）
            closed: 是否已关闭（默认false）
            limit: 返回数量限制（默认100）
            
        Returns:
            list: 市场列表
        """
        return self.get_markets(event_id=event_id, active=active, closed=closed, limit=limit)
    
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(requests.RequestException,),
        log_func=logger.warning
    )
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
        
        url = f"{self.gamma_api_url}/markets/{market_id}"
        response = requests.get(url, timeout=self.api_timeout or 10)
        response.raise_for_status()
        return response.json()
    
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
        # 首先从数据库中获取价格数据
        try:
            from database.database_manager import db_manager
            db_manager.connect()
            
            # 从数据库中查询价格数据
            query = "SELECT last_price, bid, ask, volume FROM market_prices WHERE market_id = %s"
            result = db_manager.execute_query(query, (market_id,))
            
            if result and len(result) > 0:
                price_data = result[0]
                logger.info(f"从数据库获取市场 {market_id} 价格: {price_data}")
                return {
                    "market_id": market_id,
                    "last_price": str(price_data['last_price']),
                    "bid": str(price_data['bid']),
                    "ask": str(price_data['ask']),
                    "volume": str(price_data['volume'])
                }
        except Exception as e:
            logger.error(f"从数据库获取市场价格失败: {e}")
        
        # 如果数据库中没有数据，使用模拟数据
        if self.mock:
            # 模拟数据
            return {
                "market_id": market_id,
                "last_price": "0.645",
                "bid": "0.64",
                "ask": "0.65",
                "volume": "10000"
            }
        
        # 真实模式下从API获取数据
        try:
            url = f"{self.clob_api_url}/price/{market_id}"
            response = requests.get(url)
            
            # 处理404错误（市场不存在）
            if response.status_code == 404:
                logger.warning(f"市场 {market_id} 不存在或已关闭，返回默认价格")
                return {
                    "market_id": market_id,
                    "last_price": "0",
                    "bid": "0",
                    "ask": "0",
                    "volume": "0"
                }
            
            response.raise_for_status()
            price_data = response.json()
            
            # 将数据保存到数据库
            try:
                from database.database_manager import db_manager
                db_manager.connect()
                
                # 插入或更新价格数据
                insert_query = """
                INSERT INTO market_prices (market_id, last_price, bid, ask, volume)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    last_price = VALUES(last_price),
                    bid = VALUES(bid),
                    ask = VALUES(ask),
                    volume = VALUES(volume)
                """
                
                db_manager.execute_update(
                    insert_query,
                    (
                        market_id,
                        float(price_data.get('last_price', '0')),
                        float(price_data.get('bid', '0')),
                        float(price_data.get('ask', '0')),
                        float(price_data.get('volume', '0'))
                    )
                )
                logger.info(f"市场 {market_id} 价格已保存到数据库")
            except Exception as db_error:
                logger.error(f"保存市场价格到数据库失败: {db_error}")
            
            return price_data
        except Exception as e:
            logger.error(f"获取市场价格失败: {e}")
            return {"last_price": "0", "bid": "0", "ask": "0", "volume": "0"}
    
    def get_order_status(self, order_id: str) -> dict:
        """获取订单状态
        
        Args:
            order_id: 网关订单ID
            
        Returns:
            dict: 订单状态信息
        """
        if self.mock:
            # 模拟订单状态数据
            import random
            statuses = ['filled', 'partially_filled', 'submitted']
            status = random.choice(statuses)
            
            if status == 'partially_filled':
                filled_qty = random.uniform(0.1, 0.9)
            elif status == 'filled':
                filled_qty = 1.0
            else:
                filled_qty = 0.0
            
            return {
                'status': status,
                'filled_quantity': filled_qty,
                'remaining_quantity': 1.0 - filled_qty,
                'average_price': random.uniform(0.4, 0.6),
                'timestamp': time.time()
            }
        
        try:
            # 这里应该调用Polymarket API获取订单状态
            # 由于实际API可能不同，这里返回模拟数据
            import random
            statuses = ['filled', 'partially_filled', 'submitted']
            status = random.choice(statuses)
            
            if status == 'partially_filled':
                filled_qty = random.uniform(0.1, 0.9)
            elif status == 'filled':
                filled_qty = 1.0
            else:
                filled_qty = 0.0
            
            return {
                'status': status,
                'filled_quantity': filled_qty,
                'remaining_quantity': 1.0 - filled_qty,
                'average_price': random.uniform(0.4, 0.6),
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"获取订单状态失败: {e}")
            return {'status': 'error', 'error': str(e)}
    
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
            # 尝试使用不同的API端点获取持仓数据
            target_address = address or self.address
            
            # 尝试1: 使用data-api的positions端点
            try:
                url = f"{self.data_api_url}/positions/{target_address}"
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                positions = response.json()
                logger.info(f"使用data-api获取持仓成功: {positions}")
                return positions
            except Exception as e:
                logger.warning(f"使用data-api获取持仓失败: {e}")
            
            # 尝试2: 使用gamma-api的positions端点
            try:
                url = f"{self.gamma_api_url}/positions"
                params = {"address": target_address}
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                response = requests.get(url, params=params, headers=headers)
                response.raise_for_status()
                positions = response.json()
                logger.info(f"使用gamma-api获取持仓成功: {positions}")
                return positions
            except Exception as e:
                logger.warning(f"使用gamma-api获取持仓失败: {e}")
            
            # 尝试3: 使用clob-api的positions端点
            try:
                url = f"{self.clob_api_url}/positions"
                params = {"address": target_address}
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                response = requests.get(url, params=params, headers=headers)
                response.raise_for_status()
                positions = response.json()
                logger.info(f"使用clob-api获取持仓成功: {positions}")
                return positions
            except Exception as e:
                logger.warning(f"使用clob-api获取持仓失败: {e}")
            
            # 所有尝试都失败，返回空列表
            logger.error("所有获取持仓的尝试都失败")
            return []
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
            # 尝试使用data-api获取投资组合数据
            if address:
                url = f"{self.data_api_url}/portfolio/{address}"
            else:
                url = f"{self.data_api_url}/portfolio/{self.address}"
            response = requests.get(url)
            response.raise_for_status()
            portfolio_data = response.json()
            logger.info(f"使用data-api获取投资组合数据成功: {portfolio_data}")
            return portfolio_data
        except Exception as e:
            logger.error(f"使用data-api获取投资组合数据失败: {e}")
            
            # 尝试使用get_positions方法获取持仓数据，并计算投资组合数据
            try:
                positions = self.get_positions(address)
                if positions:
                    total_value = 0.0
                    total_pnl = 0.0
                    portfolio_positions = []
                    
                    for position in positions:
                        # 计算每个持仓的价值
                        size = float(position.get('size', '0'))
                        current_price = float(position.get('current_price', '0'))
                        value = size * current_price
                        pnl = float(position.get('pnl', '0'))
                        
                        total_value += value
                        total_pnl += pnl
                        
                        portfolio_positions.append({
                            "market_id": position.get('market_id', ''),
                            "outcome": position.get('outcome', ''),
                            "value": str(round(value, 2)),
                            "pnl": str(round(pnl, 2))
                        })
                    
                    # 构建投资组合数据
                    portfolio_data = {
                        "total_value": str(round(total_value, 2)),
                        "total_pnl": str(round(total_pnl, 2)),
                        "positions": portfolio_positions,
                        "stats": {
                            "total_trades": len(positions),
                            "win_rate": sum(1 for p in positions if float(p.get('pnl', '0')) > 0) / len(positions) if positions else 0,
                            "avg_win": sum(float(p.get('pnl', '0')) for p in positions if float(p.get('pnl', '0')) > 0) / sum(1 for p in positions if float(p.get('pnl', '0')) > 0) if sum(1 for p in positions if float(p.get('pnl', '0')) > 0) > 0 else 0,
                            "avg_loss": sum(abs(float(p.get('pnl', '0'))) for p in positions if float(p.get('pnl', '0')) < 0) / sum(1 for p in positions if float(p.get('pnl', '0')) < 0) if sum(1 for p in positions if float(p.get('pnl', '0')) < 0) > 0 else 0
                        }
                    }
                    
                    logger.info(f"通过持仓数据计算投资组合数据成功: {portfolio_data}")
                    return portfolio_data
            except Exception as e:
                logger.error(f"通过持仓数据计算投资组合数据失败: {e}")
            
            # 所有尝试都失败，返回默认数据
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
    
    def get_balance(self, address: str = None) -> dict:
        """获取账户余额
        
        Args:
            address: 用户钱包地址（可选）
            
        Returns:
            dict: 账户余额数据
        """
        if self.mock:
            # 模拟数据
            return {
                "usdc": "10000.0",
                "usd": "10000.0"
            }
        
        try:
            # 优先使用USDC合约查询余额（最可靠的方式）
            target_address = address or self.address
            
            try:
                if self.usdc_address and self.w3.is_connected():
                    # USDC合约ABI
                    usdc_abi = [
                        {
                            "constant": True,
                            "inputs": [{"name": "_owner", "type": "address"}],
                            "name": "balanceOf",
                            "outputs": [{"name": "", "type": "uint256"}],
                            "payable": False,
                            "stateMutability": "view",
                            "type": "function"
                        },
                        {
                            "constant": True,
                            "inputs": [],
                            "name": "decimals",
                            "outputs": [{"name": "", "type": "uint8"}],
                            "payable": False,
                            "stateMutability": "view",
                            "type": "function"
                        }
                    ]
                    usdc_contract = self.w3.eth.contract(address=self.usdc_address, abi=usdc_abi)
                    balance = usdc_contract.functions.balanceOf(target_address).call()
                    decimals = usdc_contract.functions.decimals().call()
                    usdc_balance = balance / (10 ** decimals)
                    logger.info(f"通过合约查询USDC余额成功: {usdc_balance}")
                    return {
                        "usdc": str(usdc_balance),
                        "usd": str(usdc_balance)  # 简化处理，假设1 USDC = 1 USD
                    }
            except Exception as e:
                logger.warning(f"通过合约查询余额失败: {e}")
            
            # 如果合约查询失败，尝试使用API端点
            # 尝试1: 使用gamma-api的balances端点
            try:
                url = f"{self.gamma_api_url}/balances"
                params = {"address": target_address}
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                response = requests.get(url, params=params, headers=headers)
                response.raise_for_status()
                balance_data = response.json()
                logger.info(f"使用gamma-api获取余额成功: {balance_data}")
                return {
                    "usdc": str(balance_data.get("usdc", 0)),
                    "usd": str(balance_data.get("usd", 0))
                }
            except Exception as e:
                logger.warning(f"使用gamma-api获取余额失败: {e}")
            
            # 尝试2: 使用clob-api的balances端点
            try:
                url = f"{self.clob_api_url}/balances"
                params = {"address": target_address}
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                response = requests.get(url, params=params, headers=headers)
                response.raise_for_status()
                balance_data = response.json()
                logger.info(f"使用clob-api获取余额成功: {balance_data}")
                return {
                    "usdc": str(balance_data.get("usdc", 0)),
                    "usd": str(balance_data.get("usd", 0))
                }
            except Exception as e:
                logger.warning(f"使用clob-api获取余额失败: {e}")
            
            # 尝试3: 使用data-api的wallet端点
            try:
                url = f"{self.data_api_url}/wallet/{target_address}"
                response = requests.get(url)
                response.raise_for_status()
                balance_data = response.json()
                logger.info(f"使用data-api获取余额成功: {balance_data}")
                return {
                    "usdc": str(balance_data.get("usdc_balance", 0)),
                    "usd": str(balance_data.get("usd_value", 0))
                }
            except Exception as e:
                logger.warning(f"使用data-api获取余额失败: {e}")
            
            # 所有尝试都失败，返回默认余额
            logger.error("所有获取余额的尝试都失败")
            return {
                "usdc": "0.0",
                "usd": "0.0"
            }
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            # 返回默认余额
            return {
                "usdc": "0.0",
                "usd": "0.0"
            }
    
    def withdraw(self, amount: float, destination: str, asset: str = "USDC") -> dict:
        """提现功能
        
        Args:
            amount: 提现金额
            destination: 目标地址
            asset: 提现资产类型
            
        Returns:
            dict: 提现结果
        """
        if self.mock:
            # 模拟提现
            withdraw_id = f"withdraw_{int(time.time())}"
            logger.info(f"[MOCK] 提现成功: {amount} {asset} 到地址 {destination}")
            return {
                "id": withdraw_id,
                "status": "completed",
                "amount": amount,
                "asset": asset,
                "destination": destination,
                "timestamp": time.time()
            }
        
        try:
            # 构建提现请求
            url = f"{self.withdraw_api_url}/withdraw"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
            }
            
            withdraw_data = {
                "amount": amount,
                "destination": destination,
                "asset": asset
            }
            
            response = requests.post(url, json=withdraw_data, headers=headers)
            response.raise_for_status()
            withdraw_result = response.json()
            
            logger.info(f"提现成功: {withdraw_result}")
            return withdraw_result
        except Exception as e:
            logger.error(f"提现失败: {e}")
            return {"error": str(e)}
    
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
    
    def create_order(self, market_id: str, outcome: str, price: float, size: float, side: str = 'buy') -> dict:
        """创建订单
        
        Args:
            market_id: 市场ID
            outcome: 结果选项（Yes/No）
            price: 价格
            size: 数量
            side: 买卖方向（buy/sell）
            
        Returns:
            dict: 订单信息
        """
        if self.mock:
            # 模拟订单
            order_id = f"order_{int(time.time())}"
            logger.info(f"[MOCK] 创建订单: {order_id}, 市场: {market_id}, 结果: {outcome}, 价格: {price}, 数量: {size}, 方向: {side}")
            return {
                "order_id": order_id,
                "market_id": market_id,
                "outcome": outcome,
                "price": price,
                "size": size,
                "side": side,
                "status": "submitted",
                "timestamp": time.time()
            }
        
        try:
            # 获取市场详情，获取token ID
            market = self.get_market(market_id)
            clob_token_ids = market.get('clobTokenIds', [])
            
            if len(clob_token_ids) < 2:
                logger.error(f"市场 {market_id} 没有有效的token ID")
                return {"error": "市场没有有效的token ID"}
            
            # 根据结果选项选择token ID
            if outcome.lower() == 'yes':
                token_id = clob_token_ids[0]
            elif outcome.lower() == 'no':
                token_id = clob_token_ids[1]
            else:
                logger.error(f"无效的结果选项: {outcome}")
                return {"error": "无效的结果选项"}
            
            # 获取市场详情，获取tick size和neg risk
            market_detail = self.get_market(market_id)
            tick_size = str(market_detail.get('minimum_tick_size', '0.01'))
            neg_risk = market_detail.get('neg_risk', False)
            
            # 构建订单参数
            order_args = {
                "token_id": token_id,
                "price": price,
                "size": size,
                "side": side,
                "order_type": "GTC"
            }
            
            # 使用CLOB API下单
            url = f"{self.clob_api_url}/order"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
            }
            
            # 构建订单数据
            order_data = {
                "order": order_args,
                "options": {
                    "tick_size": tick_size,
                    "neg_risk": neg_risk
                }
            }
            
            response = requests.post(url, json=order_data, headers=headers)
            response.raise_for_status()
            order_result = response.json()
            
            logger.info(f"订单创建成功: {order_result}")
            return order_result
        except Exception as e:
            logger.error(f"创建订单失败: {e}")
            return {"error": str(e)}
    
    def calculate_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """计算凯利公式
        
        Args:
            win_rate: 胜率
            avg_win: 平均盈利
            avg_loss: 平均亏损
            
        Returns:
            float: 凯利公式结果
        """
        if avg_win == 0:
            return 0.0
        
        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        
        # 确保结果在合理范围内
        kelly_fraction = max(0.0, min(kelly_fraction, 1.0))
        
        return kelly_fraction
    
    def check_trigger_and_execute(self, market_id: str, outcome: str, trigger_price: float, win_rate: float, avg_win: float, avg_loss: float, balance: float) -> dict:
        """检查触发条件并执行交易
        
        Args:
            market_id: 市场ID
            outcome: 结果选项（Yes/No）
            trigger_price: 触发购买值
            win_rate: 胜率
            avg_win: 平均盈利
            avg_loss: 平均亏损
            balance: 账户余额
            
        Returns:
            dict: 交易结果
        """
        try:
            # 获取当前市场价格
            price_data = self.get_market_price(market_id)
            current_price = float(price_data.get('last_price', '0'))
            
            # 检查是否达到触发条件
            if current_price <= trigger_price:
                # 计算凯利公式
                kelly_fraction = self.calculate_kelly_fraction(win_rate, avg_win, avg_loss)
                
                # 计算下单数量
                order_size = balance * kelly_fraction
                
                # 创建订单
                order_result = self.create_order(market_id, outcome, trigger_price, order_size, 'buy')
                
                logger.info(f"触发条件满足，已执行交易: {order_result}")
                return {
                    "triggered": True,
                    "current_price": current_price,
                    "trigger_price": trigger_price,
                    "kelly_fraction": kelly_fraction,
                    "order_size": order_size,
                    "order_result": order_result
                }
            else:
                return {
                    "triggered": False,
                    "current_price": current_price,
                    "trigger_price": trigger_price
                }
        except Exception as e:
            logger.error(f"检查触发条件并执行交易失败: {e}")
            return {
                "error": str(e)
            }
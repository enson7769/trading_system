from web3 import Web3
from eth_account import Account
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

    def connect(self):
        """连接到Polymarket"""
        if self.mock:
            # 模拟模式：跳过实际连接，使用测试数据
            self.private_key = "0x" + "a" * 64  # 模拟私钥
            self.address = "0xMockAddress12345678901234567890123456789012"
            logger.info(f"[MOCK] 已连接Polymarket钱包: {self.address[:6]}...{self.address[-4:]}")
            return

        if not self.w3.is_connected():
            raise ConnectionError("连接RPC失败")

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
        # === 模拟交易（实际部署时替换为真实 Web3 调用）===
        tx_hash = self._simulate_trade(order)
        logger.info(f"已模拟Polymarket订单: {tx_hash}")
        return tx_hash

    def _simulate_trade(self, order) -> str:
        """模拟交易，返回假的交易哈希"""
        import time
        time.sleep(0.1)  # 模拟网络延迟
        return "0x" + "a1b2c3d4e5f6" * 5  # 假的交易哈希
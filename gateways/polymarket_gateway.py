from web3 import Web3
from eth_account import Account
from core.models import Order, Instrument
from gateways.base import BaseGateway
from utils.logger import logger
from security.credential_manager import CredentialManager
from config.config import config

class PolymarketGateway(BaseGateway):
    def __init__(self, rpc_url: str, credential_manager: CredentialManager, mock: bool = None):
        super().__init__("polymarket")
        # Load configuration
        gateway_config = config.get_gateway_config('polymarket')
        
        # Use provided value or config value or default
        if mock is None:
            mock = gateway_config.get('mock', True)
        
        self.rpc_url = rpc_url
        self.cred_mgr = credential_manager
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.private_key = None
        self.address = None
        self.no_input = False
        self.mock = mock
        # Load contract addresses from config
        self.exchange_address = gateway_config.get('exchange_address', "0x435AB6645531D3f5391E8B8DA9c0F7b64e6C7e11")
        self.usdc_address = gateway_config.get('usdc_address', "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

    def connect(self):
        if self.mock:
            # Mock mode: Skip actual connection and use test data
            self.private_key = "0x" + "a" * 64  # Mock private key
            self.address = "0xMockAddress12345678901234567890123456789012"
            logger.info(f"[MOCK] Connected Polymarket wallet: {self.address[:6]}...{self.address[-4:]}")
            return

        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to RPC")

        self.private_key = self.cred_mgr.get_secret(
            key="polymarket_private_key",
            prompt="Enter Polymarket wallet private key (hidden): ",
            env_var="POLYMARKET_PRIVATE_KEY",
            no_input=self.no_input
        )
        
        # Validate private key format
        if not self._validate_private_key(self.private_key):
            raise ValueError("Invalid private key format. Please provide a valid 64-character hexadecimal string.")
        
        account = Account.from_key(self.private_key)
        self.address = account.address
        logger.info(f"Connected Polymarket wallet: {self.address[:6]}...{self.address[-4:]}")
    
    def _validate_private_key(self, private_key: str) -> bool:
        """Validate that the private key is a valid hexadecimal string"""
        # Remove 0x prefix if present
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        
        # Check length (64 hex characters = 32 bytes)
        if len(private_key) != 64:
            return False
        
        # Check if all characters are hexadecimal
        try:
            int(private_key, 16)
            return True
        except ValueError:
            return False

    def send_order(self, order: Order) -> str:
        # === 模拟交易（实际部署时替换为真实 Web3 调用）===
        tx_hash = self._simulate_trade(order)
        logger.info(f"Simulated Polymarket order: {tx_hash}")
        return tx_hash

    def _simulate_trade(self, order) -> str:
        """模拟交易，返回 fake tx hash"""
        import time
        time.sleep(0.1)  # 模拟网络延迟
        return "0x" + "a1b2c3d4e5f6" * 5  # fake tx hash
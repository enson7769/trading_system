from core.models import Order
from gateways.base import BaseGateway
from utils.logger import logger
from security.credential_manager import CredentialManager
from config.config import config
import requests
import time
import hmac
import hashlib

class BinanceGateway(BaseGateway):
    """币安交易网关"""
    
    def __init__(self, credential_manager: CredentialManager, mock: bool = None):
        """初始化币安网关
        
        Args:
            credential_manager: 凭证管理器
            mock: 是否启用模拟模式
        """
        super().__init__("binance")
        # 加载配置
        gateway_config = config.get_gateway_config('binance')
        
        # 使用提供的值或配置值或默认值
        if mock is None:
            mock = gateway_config.get('mock', True)
        
        self.cred_mgr = credential_manager
        self.mock = mock
        self.api_key = None
        self.api_secret = None
        self.base_url = gateway_config.get('base_url', 'https://api.binance.com')
        self.testnet = gateway_config.get('testnet', False)
        
        if self.testnet:
            self.base_url = 'https://testnet.binance.vision'
        
        self.no_input = False
    
    def connect(self):
        """连接到币安API"""
        if self.mock:
            # 模拟模式：跳过实际连接，使用测试数据
            self.api_key = "mock_api_key"
            self.api_secret = "mock_api_secret"
            logger.info("[MOCK] 已连接到币安API")
            return True
        
        # 获取API密钥
        self.api_key = self.cred_mgr.get_secret(
            key="binance_api_key",
            prompt="输入币安API密钥: ",
            env_var="BINANCE_API_KEY",
            no_input=self.no_input
        )
        
        self.api_secret = self.cred_mgr.get_secret(
            key="binance_api_secret",
            prompt="输入币安API密钥密码 (隐藏): ",
            env_var="BINANCE_API_SECRET",
            no_input=self.no_input
        )
        
        # 验证连接
        if not self._test_connection():
            raise ConnectionError("连接币安API失败")
        
        logger.info("已成功连接到币安API")
        return True
    
    def _test_connection(self) -> bool:
        """测试与币安API的连接"""
        try:
            url = f"{self.base_url}/api/v3/ping"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"测试币安连接错误: {e}")
            return False
    
    def _sign_request(self, params: dict) -> dict:
        """为请求签名"""
        timestamp = int(time.time() * 1000)
        params['timestamp'] = timestamp
        
        # 创建签名
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        params['signature'] = signature
        return params
    
    def _send_request(self, method: str, endpoint: str, params: dict = None, signed: bool = False) -> dict:
        """发送请求到币安API"""
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        if signed and params:
            params = self._sign_request(params)
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, params=params, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, params=params, headers=headers, timeout=10)
            else:
                raise ValueError(f"不支持的方法: {method}")
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"发送请求到币安错误: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应: {e.response.text}")
            raise
    
    def send_order(self, order: Order) -> str:
        """发送订单到币安"""
        if self.mock:
            # 模拟模式
            order_id = f"MOCK_{int(time.time())}"
            logger.info(f"[MOCK] 已发送订单到币安: {order_id}")
            return order_id
        
        params = {
            'symbol': order.instrument.replace('/', ''),
            'side': order.side.upper(),
            'type': order.type.upper(),
            'quantity': order.quantity,
            'price': order.price
        }
        
        response = self._send_request('POST', '/api/v3/order', params, signed=True)
        order_id = response.get('orderId')
        logger.info(f"已发送订单到币安: {order_id}")
        return str(order_id)
    
    def withdraw(self, coin: str, amount: float, address: str, network: str = None) -> dict:
        """从币安提现"""
        if self.mock:
            # 模拟模式
            tx_id = f"MOCK_WD_{int(time.time())}"
            logger.info(f"[MOCK] 已提现 {amount} {coin} 到 {address}")
            return {
                'success': True,
                'txId': tx_id,
                'amount': amount,
                'coin': coin,
                'address': address
            }
        
        params = {
            'coin': coin,
            'amount': amount,
            'address': address
        }
        
        if network:
            params['network'] = network
        
        response = self._send_request('POST', '/sapi/v1/capital/withdraw/apply', params, signed=True)
        logger.info(f"已提现 {amount} {coin} 到 {address}, txId: {response.get('id')}")
        return response
    
    def deposit_history(self, coin: str = None, status: int = None, start_time: int = None, end_time: int = None, limit: int = 100) -> list:
        """获取充值历史"""
        if self.mock:
            # 模拟模式
            mock_data = [
                {
                    'amount': 100.0,
                    'coin': coin or 'USDC',
                    'network': 'BSC',
                    'status': 1,
                    'address': '0xDepositAddress1234567890',
                    'txId': '0xMockTxId1234567890',
                    'insertTime': int(time.time() * 1000) - 3600000,
                    'transferType': 0
                }
            ]
            logger.info(f"[MOCK] 已获取 {coin or '所有币种'} 的充值历史")
            return mock_data
        
        params = {'limit': limit}
        
        if coin:
            params['coin'] = coin
        if status:
            params['status'] = status
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        response = self._send_request('GET', '/sapi/v1/capital/deposit/hisrec', params, signed=True)
        logger.info(f"已获取 {len(response)} 条充值记录")
        return response
    
    def withdraw_history(self, coin: str = None, status: int = None, start_time: int = None, end_time: int = None, limit: int = 100) -> list:
        """获取提现历史"""
        if self.mock:
            # 模拟模式
            mock_data = [
                {
                    'amount': 50.0,
                    'coin': coin or 'USDC',
                    'network': 'BSC',
                    'status': 6,
                    'address': '0xWithdrawAddress1234567890',
                    'txId': '0xMockTxId1234567890',
                    'applyTime': int(time.time() * 1000) - 7200000,
                    'successTime': int(time.time() * 1000) - 7100000
                }
            ]
            logger.info(f"[MOCK] 已获取 {coin or '所有币种'} 的提现历史")
            return mock_data
        
        params = {'limit': limit}
        
        if coin:
            params['coin'] = coin
        if status:
            params['status'] = status
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        response = self._send_request('GET', '/sapi/v1/capital/withdraw/history', params, signed=True)
        logger.info(f"已获取 {len(response)} 条提现记录")
        return response
    
    def get_account_balance(self, coin: str = None) -> dict:
        """获取账户余额"""
        if self.mock:
            # 模拟模式
            mock_balance = {
                'USDC': 10000.0,
                'BTC': 1.0,
                'ETH': 10.0
            }
            if coin:
                logger.info(f"[MOCK] 已获取 {coin} 的余额: {mock_balance.get(coin, 0)}")
                return {coin: mock_balance.get(coin, 0)}
            logger.info("[MOCK] 已获取账户余额")
            return mock_balance
        
        response = self._send_request('GET', '/api/v3/account', {}, signed=True)
        balances = {}
        
        for asset in response.get('balances', []):
            free = float(asset.get('free', '0'))
            locked = float(asset.get('locked', '0'))
            total = free + locked
            if total > 0:
                balances[asset.get('asset')] = total
        
        if coin:
            logger.info(f"已获取 {coin} 的余额: {balances.get(coin, 0)}")
            return {coin: balances.get(coin, 0)}
        
        logger.info(f"已获取 {len(balances)} 个资产的余额")
        return balances

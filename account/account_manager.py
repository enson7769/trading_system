from decimal import Decimal
from typing import Dict
from core.models import AccountInfo

class AccountManager:
    """账户管理器"""
    
    def __init__(self):
        """初始化账户管理器"""
        # 存储账户信息的字典
        self.accounts: Dict[str, AccountInfo] = {}

    def add_account(self, account_id: str, gateway_name: str, initial_balances: dict):
        """添加账户
        
        Args:
            account_id: 账户ID
            gateway_name: 网关名称
            initial_balances: 初始余额
        """
        self.accounts[account_id] = AccountInfo(
            account_id=account_id,
            gateway_name=gateway_name,
            balances={k: Decimal(str(v)) for k, v in initial_balances.items()},
            positions={}
        )

    def get_account(self, account_id: str) -> AccountInfo:
        """获取账户信息
        
        Args:
            account_id: 账户ID
            
        Returns:
            AccountInfo: 账户信息对象
        """
        return self.accounts[account_id]
from decimal import Decimal
from typing import Dict
from core.models import AccountInfo

class AccountManager:
    def __init__(self):
        self.accounts: Dict[str, AccountInfo] = {}

    def add_account(self, account_id: str, gateway_name: str, initial_balances: dict):
        self.accounts[account_id] = AccountInfo(
            account_id=account_id,
            gateway_name=gateway_name,
            balances={k: Decimal(str(v)) for k, v in initial_balances.items()},
            positions={}
        )

    def get_account(self, account_id: str) -> AccountInfo:
        return self.accounts[account_id]
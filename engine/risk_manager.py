from decimal import Decimal
from core.models import AccountInfo, Order

class RiskManager:
    def check_order(self, account: AccountInfo, order: Order) -> bool:
        # 简单风控：检查 USDC 余额
        cost = order.quantity * (order.price or Decimal('1'))
        usdc_balance = account.balances.get("USDC", Decimal('0'))
        if usdc_balance < cost:
            return False
        return True
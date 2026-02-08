from enum import Enum

class OrderSide(Enum):
    """订单方向枚举"""
    BUY = "buy"  # 买入
    SELL = "sell"  # 卖出

class OrderType(Enum):
    """订单类型枚举"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"  # 限价单

class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"  # 待处理
    SUBMITTED = "submitted"  # 已提交
    PARTIALLY_FILLED = "partially_filled"  # 部分成交
    FILLED = "filled"  # 已成交
    CANCELLED = "cancelled"  # 已取消
    REJECTED = "rejected"  # 已拒绝
    EXPIRED = "expired"  # 已过期
    ERROR = "error"  # 错误
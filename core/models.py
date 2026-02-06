from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict
from .enums import OrderSide, OrderType, OrderStatus

@dataclass
class Instrument:
    """交易对信息"""
    symbol: str  # 交易对符号
    base_asset: str  # 基础资产
    quote_asset: str  # 报价资产
    min_order_size: Decimal  # 最小订单大小
    tick_size: Decimal  # 价格跳动幅度
    gateway_name: str  # 所属网关名称

@dataclass
class Order:
    """订单信息"""
    order_id: str  # 订单ID
    instrument: Instrument  # 交易对
    side: OrderSide  # 订单方向
    type: OrderType  # 订单类型
    quantity: Decimal  # 订单数量
    price: Optional[Decimal] = None  # 订单价格（市价单为None）
    status: OrderStatus = OrderStatus.PENDING  # 订单状态
    filled_qty: Decimal = field(default_factory=lambda: Decimal('0'))  # 已成交数量
    gateway_order_id: Optional[str] = None  # 网关订单ID
    account_id: Optional[str] = None  # 账户ID
    outcome: Optional[str] = None  # 结果选项（Polymarket特有）

@dataclass
class Position:
    """持仓信息"""
    instrument: Instrument  # 交易对
    size: Decimal  # 持仓大小
    avg_price: Decimal  # 平均持仓价格

@dataclass
class AccountInfo:
    """账户信息"""
    account_id: str  # 账户ID
    gateway_name: str  # 所属网关名称
    balances: Dict[str, Decimal]  # 账户余额
    positions: Dict[str, Position] = field(default_factory=dict)  # 持仓信息
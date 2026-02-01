from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict
from .enums import OrderSide, OrderType, OrderStatus

@dataclass
class Instrument:
    symbol: str
    base_asset: str
    quote_asset: str
    min_order_size: Decimal
    tick_size: Decimal
    gateway_name: str

@dataclass
class Order:
    order_id: str
    instrument: Instrument
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: Decimal = field(default_factory=lambda: Decimal('0'))
    gateway_order_id: Optional[str] = None
    account_id: Optional[str] = None

@dataclass
class Position:
    instrument: Instrument
    size: Decimal
    avg_price: Decimal

@dataclass
class AccountInfo:
    account_id: str
    gateway_name: str
    balances: Dict[str, Decimal]
    positions: Dict[str, Position] = field(default_factory=dict)
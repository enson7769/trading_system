from abc import ABC, abstractmethod
from typing import Callable
from core.models import Order

class BaseGateway(ABC):
    """网关抽象基类"""
    
    def __init__(self, name: str):
        """初始化网关
        
        Args:
            name: 网关名称
        """
        self.name = name
        # 订单更新回调函数
        self.on_order_update: Callable[[Order], None] = lambda o: None

    @abstractmethod
    def connect(self):
        """连接到交易平台"""
        pass

    @abstractmethod
    def send_order(self, order: Order) -> str:
        """发送订单到交易平台
        
        Args:
            order: 订单对象
            
        Returns:
            交易平台返回的订单ID
        """
        pass
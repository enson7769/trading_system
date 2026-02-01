from abc import ABC, abstractmethod
from typing import Callable
from core.models import Order

class BaseGateway(ABC):
    def __init__(self, name: str):
        self.name = name
        self.on_order_update: Callable[[Order], None] = lambda o: None

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def send_order(self, order: Order) -> str:
        pass